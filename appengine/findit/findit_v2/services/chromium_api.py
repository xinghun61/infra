# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the chromium-specific APIs required by Findit."""

from collections import defaultdict

from findit_v2.services.failure_type import StepTypeEnum
from findit_v2.services.project_api import ProjectAPI

from common.findit_http_client import FinditHttpClient
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

  def GetCompileFailures(self, build, compile_steps):  # pragma: no cover.
    raise NotImplementedError

  def GetTestFailures(self, build, test_steps):  # pragma: no cover.
    raise NotImplementedError

  def GetRerunBuilderId(self, build):  # pragma: no cover.
    raise NotImplementedError

  def GetTestRerunBuildInputProperties(self, tests):  # pragma: no cover.
    raise NotImplementedError

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
