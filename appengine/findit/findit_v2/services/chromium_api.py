# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the chromium-specific APIs required by Findit."""

from collections import defaultdict
import json
import logging

from google.protobuf.field_mask_pb2 import FieldMask

from findit_v2.services.failure_type import StepTypeEnum
from findit_v2.services.project_api import ProjectAPI

from common.findit_http_client import FinditHttpClient
from common.waterfall import buildbucket_client
from infra_api_clients import logdog_util
from services import git
from services.compile_failure import extract_compile_signal
from services.compile_failure import compile_failure_analysis
from services.test_failure import extract_test_signal
from services.test_failure import test_failure_analysis
from services.parameters import CompileFailureInfo
from services.parameters import TestFailureInfo
from waterfall import build_util


class ChromiumProjectAPI(ProjectAPI):

  def ExtractSignalsForCompileFailure(self, failure_info):
    return extract_compile_signal.ExtractSignalsForCompileFailure(
        failure_info, FinditHttpClient())

  def ExtractSignalsForTestFailure(self, failure_info):
    return extract_test_signal.ExtractSignalsForTestFailure(
        failure_info, FinditHttpClient())

  def ClassifyStepType(self, _build, step):
    if step.name == 'compile':
      return StepTypeEnum.COMPILE

    for log in step.logs:
      if log.name == 'step_metadata':
        return StepTypeEnum.TEST

    return StepTypeEnum.INFRA

  def GetCompileFailures(self, build, compile_steps):
    """Returns the detailed compile failures from a failed build.

    For Chromium builds, the failure details are found in the ninja_info json
    log of the failed compile step.

    Although there's usually one compile step per build, this implementation
    can potentially handle multiple.
    """
    build_info = {
        'id': build.id,
        'number': build.number,
        'commit_id': build.input.gitiles_commit.id
    }
    ninja_infos = {}
    for step in compile_steps or []:
      for log in step.logs or []:
        if log.name.lower() == 'json.output[ninja_info]':
          ninja_infos[step.name] = logdog_util.GetLogFromViewUrl(
              log.view_url, FinditHttpClient())

    result = {}
    for step_name, ninja_info in ninja_infos.iteritems():
      if isinstance(ninja_info, basestring):
        ninja_info = json.loads(ninja_info)
      for failure in ninja_info.get('failures', []):
        failed_targets = failure.get('output_nodes')
        rule = failure.get('rule')
        if failed_targets:
          logging.info('Found the following failed targets in step %s: %s',
                       step_name, ', '.join(failed_targets))
          result.setdefault(step_name, {'failures': {}})
          result[step_name]['failures'][frozenset(failed_targets)] = {
              'properties': {
                  'rule': rule
              },
              'first_failed_build': build_info,
              'last_passed_build': None,
          }
    return result

  def GetTestFailures(self, build, test_steps):  # pragma: no cover.
    raise NotImplementedError

  def GetRerunBuilderId(self, _build):
    return '{project}/{bucket}/{builder}'.format(
        project='chromium', bucket='findit', builder='findit-rerun')

  def GetCompileRerunBuildInputProperties(self, failed_targets,
                                          analyzed_build_id):
    all_targets = set()
    for step, targets in failed_targets.iteritems():
      # Assume the step is a compile step.
      assert step == 'compile'
      all_targets |= set(targets)

    properties = {}
    build = buildbucket_client.GetV2Build(
        analyzed_build_id,
        fields=FieldMask(paths=['input.properties', 'builder']))
    properties['target_builder'] = {
        'master': build.input.properties['mastername'],
        'builder': build.builder.builder
    }
    properties['compile_targets'] = list(all_targets)
    return properties

  def GetTestRerunBuildInputProperties(self, tests, analyzed_build_id):
    properties = {}
    build = buildbucket_client.GetV2Build(
        analyzed_build_id,
        fields=FieldMask(paths=['input.properties', 'builder']))
    properties['target_builder'] = {
        'master': build.input.properties['mastername'],
        'builder': build.builder.builder
    }
    properties['tests'] = {
        s: [t['name'] for t in tests_in_suite['tests']
           ] for s, tests_in_suite in tests.iteritems()
    }

    return properties

  def GetTestFailureInfo(self, context, build, first_failures_in_current_build):
    """Creates structured object expected by heuristic analysis code."""
    # As per common/waterfall/failure_type.py
    LEGACY_TEST_TYPE = 0x10

    build_info = build_util.GetBuildInfo(build.input.properties['mastername'],
                                         build.builder.builder, build.number)

    result = {
        'failed_steps': {},
        'master_name':
            build.input.properties['mastername'],
        'builder_name':
            build.builder.builder,
        'build_number':
            build.number,
        'parent_mastername':
            build_info.parent_mastername,
        'parent_buildername':
            build_info.parent_buildername,
        'builds': {},
        'failure_type':
            LEGACY_TEST_TYPE,
        'failed':
            True,
        'chromium_revision':
            context.gitiles_id,
        'is_luci':
            True,
        'buildbucket_bucket':
            'luci.%s.%s' % (build.builder.project, build.builder.bucket),
        'buildbucket_id':
            str(build.id),
        build.number: {
            # Construct a list of revisions since the last passing build.
            'blame_list':
                git.GetCommitsBetweenRevisionsInOrder(
                    first_failures_in_current_build['last_passed_build']
                    ['commit_id'],
                    context.gitiles_id,
                    ascending=False),
            'chromium_revision':
                context.gitiles_id,
        },
    }
    for step, failure in first_failures_in_current_build['failures'].iteritems(
    ):
      result['failed_steps'][step] = {
          'supported': True,
          'last_pass': failure['last_passed_build']['number'],
          'current_failure': build.number,
          'first_failure': build.number,
      }

    return TestFailureInfo.FromSerializable(result)

  def GetCompileFailureInfo(self, context, build,
                            first_failures_in_current_build):
    """Creates structured object expected by heuristic analysis code."""
    # As per common/waterfall/failure_type.py
    LEGACY_COMPILE_TYPE = 0x08

    return CompileFailureInfo.FromSerializable({
        'failed_steps': {
            'compile': {
                'supported':
                    True,
                'last_pass':
                    first_failures_in_current_build['last_passed_build']
                    ['number'],
                'current_failure':
                    build.number,
                'first_failure':
                    build.number,
            },
        },
        'master_name':
            build.input.properties['mastername'],
        'builder_name':
            build.builder.builder,
        'build_number':
            build.number,
        'parent_mastername':
            None,  # These only apply to some testers.
        'parent_buildername':
            None,
        'builds': {
            build.number: {
                # Construct a list of revisions since the last passing build.
                'blame_list':
                    git.GetCommitsBetweenRevisionsInOrder(
                        first_failures_in_current_build['last_passed_build']
                        ['commit_id'],
                        context.gitiles_id,
                        ascending=False),
                'chromium_revision':
                    context.gitiles_id,
            },
        },
        'failure_type':
            LEGACY_COMPILE_TYPE,
        'failed':
            True,
        'chromium_revision':
            context.gitiles_id,
        'is_luci':
            True,
        'buildbucket_bucket':
            'luci.%s.%s' % (build.builder.project, build.builder.bucket),
        'buildbucket_id':
            str(build.id),
    })

  def HeuristicAnalysisForCompile(self, failure_info, change_logs, deps_info,
                                  signals):
    failure_map, _ = compile_failure_analysis.AnalyzeCompileFailure(
        failure_info, change_logs, deps_info, signals)
    result = defaultdict(list)
    for failure in failure_map['failures']:
      # AnalyzeCompileFailure above does not associate suspects to specific
      # targets, hence we use empty frozenset() in the failure key to match the
      # suspect to all atom failures in the step.
      failure_key = (failure['step_name'], frozenset())
      for suspect in failure['suspected_cls']:
        result[failure_key].append({
            'revision': suspect['revision'],
            'commit_position': suspect['commit_position'],
            'hints': suspect['hints'],
        })
    return result

  def HeuristicAnalysisForTest(self, failure_info, change_logs, deps_info,
                               signals):
    """Performs heuristic analysis on test failures.

    Returns: Dict, mapping (<step_name>, frozenset([<failed_test>,..])) to
    {'revision': <rev>, 'commit_position': <cp>, 'hints': ['hint 1', 'hint 2']}
    Where the key identifies a failure, and the value a suspected commit.
    """
    failure_map, _ = test_failure_analysis.AnalyzeTestFailure(
        failure_info, change_logs, deps_info, signals)
    result = defaultdict(list)

    # Iterate over all failed steps.
    for failure in failure_map['failures']:
      suspects_by_cp = {}  # Suspect details indexed by commit position.
      for suspect in failure['suspected_cls']:
        suspects_by_cp[suspect['commit_position']] = {
            'revision': suspect['revision'],
            'commit_position': suspect['commit_position'],
            'hints': suspect['hints'],
        }
      # Create a mapping from suspect to tests in is suspected of breaking.
      suspected_of = defaultdict(list)  # Commit pos -> list of test names.
      for test in failure.get('tests', []):
        for test_suspect in test['suspected_cls']:
          suspected_of[test_suspect['commit_position']].append(
              test['test_name'])
      for cp, tests in suspected_of.iteritems():
        failure_key = (failure['step_name'], frozenset(tests))
        result[failure_key].append(suspects_by_cp[cp])
    return result
