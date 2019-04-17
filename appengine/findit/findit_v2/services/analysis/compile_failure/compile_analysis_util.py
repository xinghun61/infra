# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The core logic of compile analysis."""

import logging

from buildbucket_proto import common_pb2
from google.appengine.ext import ndb
from google.protobuf.field_mask_pb2 import FieldMask

from common.waterfall import buildbucket_client
from findit_v2.model.compile_failure import CompileFailure
from findit_v2.model import luci_build
from findit_v2.services import projects
from findit_v2.services.analysis import analysis_constants
from findit_v2.services.failure_type import StepTypeEnum


def SaveCompileFailures(context, build, detailed_compile_failures):
  """Saves the failed build and compile failures in data store.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    detailed_compile_failures (dict): A dict of detailed compile failures.
       {
        'build_packages': {  # compile step name.
          'failures': {
            'pkg': {  # Concatenated string of output_targets.
              'rule': 'emerge',
              'output_targets': ['pkg'],
              'first_failed_build': {
                'id': 8765432109,
                'number': 123,
                'commit_id': 654321
              },
              'last_passed_build': None
            },
            ...
          },
          'first_failed_build': {
            'id': 8765432109,
            'number': 123,
            'commit_id': 654321
          },
          'last_passed_build': None
        },
      }
  """
  build_entity = luci_build.SaveFailedBuild(context, build,
                                            StepTypeEnum.COMPILE)
  assert build_entity, 'Failed to create failure entity for build {}'.format(
      build.id)

  failed_build_key = build_entity.key
  compile_failure_entities = []
  for step_ui_name, step_info in detailed_compile_failures.iteritems():
    failures = step_info['failures']
    if not failures:
      logging.warning(
          'Cannot get detailed compile failure info for build %d,'
          ' saving step level info only.', build.id)
      new_entity = CompileFailure.Create(
          failed_build_key=failed_build_key,
          step_ui_name=step_ui_name,
          output_targets=None,
          first_failed_build_id=step_info.get('first_failed_build',
                                              {}).get('id'),
          failure_group_build_id=step_info.get('failure_group_build_id',
                                               {}).get('id'),
      )
      compile_failure_entities.append(new_entity)
      continue

    for failure in failures.itervalues():
      new_entity = CompileFailure.Create(
          failed_build_key=failed_build_key,
          step_ui_name=step_ui_name,
          output_targets=failure.get('output_targets'),
          first_failed_build_id=failure.get('first_failed_build', {}).get('id'),
          failure_group_build_id=failure.get('failure_group_build_id',
                                             {}).get('id'),
          rule=failure.get('rule'),
          dependencies=failure.get('dependencies'))
      compile_failure_entities.append(new_entity)

  ndb.put_multi(compile_failure_entities)


def _UpdateCompileFailuresWithPreviousBuildInfo(detailed_compile_failures,
                                                prev_build_info,
                                                prev_step_ui_name=None):
  """Batch updates the failures with the previous build's info."""
  for step_ui_name, step_info in detailed_compile_failures.iteritems():
    if (prev_step_ui_name and
        prev_step_ui_name != step_ui_name):  # pragma: no cover
      continue

    # Updates step level last pass build id.
    step_info[
        'last_passed_build'] = step_info['last_passed_build'] or prev_build_info

    # Updates target level last pass build id.
    failures = step_info['failures']
    for failure in failures.itervalues():
      failure[
          'last_passed_build'] = failure['last_passed_build'] or prev_build_info


def _GetPreviousCompileStepsAndFailuresInPreviousBuild(
    project_api, prev_build, detailed_compile_failures):
  """Gets compile failures in the previous build.

  Args:
    project_api (ProjectAPI): API for project specific logic.
    prev_build (buildbucket build.proto): SIMPLE info about the build.
    detailed_compile_failures (dict): A dict of detailed compile failures.
  """
  detailed_prev_build = buildbucket_client.GetV2Build(
      prev_build.id, fields=FieldMask(paths=['*']))

  # Looks for compile steps in previous build. Here only the failed compile
  # steps in current build are relevant.
  prev_compile_steps = {
      s.name: s
      for s in detailed_prev_build.steps
      if s.name in detailed_compile_failures
  }
  # Looks for compile steps that failed in both current build and this build.
  prev_failed_compile_steps = {
      step_name: step
      for step_name, step in prev_compile_steps.iteritems()
      if step.status == common_pb2.FAILURE
  }
  prev_failures = project_api.GetCompileFailures(
      detailed_prev_build,
      prev_failed_compile_steps.values()) if prev_failed_compile_steps else {}
  return prev_compile_steps, prev_failures


def DetectFirstFailures(context, build, detailed_compile_failures):
  """Updates detailed_compile_failures with first failure info.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    detailed_compile_failures (dict): A dict of detailed compile failures.
      {
        'step_name': {
          'failures': {
            'target1 target2': {
              'rule': 'emerge',
              'output_targets': ['target1', 'target2'],
              'first_failed_build': {
                'id': 8765432109,
                'number': 123,
                'commit_id': 654321
              },
              'last_passed_build': None
            },
            ...
          },
          'first_failed_build': {
            'id': 8765432109,
            'number': 123,
            'commit_id': 654321
          },
          'last_passed_build': None
        },
      }
  """

  luci_project = context.luci_project_name

  project_api = projects.GetProjectAPI(luci_project)
  assert project_api, 'Unsupported project {}'.format(luci_project)

  # Gets previous builds, the builds are sorted by build number in descending
  # order.
  # No steps info in each build considering the response size.
  # Requests to buildbucket for each failed build separately.
  search_builds_response = buildbucket_client.SearchV2BuildsOnBuilder(
      build.builder,
      create_time_range=(None, build.create_time),
      page_size=analysis_constants.MAX_BUILDS_TO_CHECK)
  previous_builds = search_builds_response.builds

  need_go_back = False
  for prev_build in previous_builds:
    prev_build_info = {
        'id': prev_build.id,
        'number': prev_build.number,
        'commit_id': prev_build.input.gitiles_commit.id
    }

    if prev_build.status == common_pb2.SUCCESS:
      # Found a passed build, update all failures.
      _UpdateCompileFailuresWithPreviousBuildInfo(detailed_compile_failures,
                                                  prev_build_info)
      return

    prev_compile_steps, prev_failures = (
        _GetPreviousCompileStepsAndFailuresInPreviousBuild(
            project_api, prev_build, detailed_compile_failures))

    for step_ui_name, step_info in detailed_compile_failures.iteritems():
      if not prev_compile_steps.get(step_ui_name):
        # For some reason the compile step didn't run in the previous build.
        need_go_back = True
        continue

      if prev_compile_steps.get(step_ui_name) and prev_compile_steps[
          step_ui_name].status == common_pb2.SUCCESS:
        # The step passed in the previous build, update all failures in this
        # step.
        _UpdateCompileFailuresWithPreviousBuildInfo(
            detailed_compile_failures,
            prev_build_info,
            prev_step_ui_name=step_ui_name)
        continue

      if not prev_failures.get(step_ui_name):
        # The step didn't pass nor fail, Findit cannot get useful information
        # from it, going back.
        need_go_back = True
        continue

      step_last_pass_found = True
      failures = step_info['failures']
      for targets_str, failure in failures.iteritems():
        if failure['last_passed_build']:
          # Last pass has been found for this failure, skip the failure.
          continue

        if prev_failures[step_ui_name]['failures'].get(targets_str):
          # The same failure happened in the previous build, going back.
          failure['first_failed_build'] = prev_build_info
          step_info['first_failed_build'] = prev_build_info
          need_go_back = True
          step_last_pass_found = False
        else:
          # The failure didn't happen in the previous build, first failure found
          failure['last_passed_build'] = prev_build_info

      if step_last_pass_found:
        step_info['last_passed_build'] = prev_build_info

    if not need_go_back:
      return
