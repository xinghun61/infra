# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logic of pre compile analysis.

Build with compile failures will be pre-processed to determine if a new compile
analysis is needed or not.
"""

import logging

from buildbucket_proto import common_pb2
from google.appengine.ext import ndb
from google.protobuf.field_mask_pb2 import FieldMask

from common.waterfall import buildbucket_client
from findit_v2.model import compile_failure
from findit_v2.model import luci_build
from findit_v2.model.compile_failure import CompileFailure
from findit_v2.model.compile_failure import CompileFailureAnalysis
from findit_v2.model.compile_failure import CompileFailureGroup
from findit_v2.services import projects
from findit_v2.services import constants
from findit_v2.services.failure_type import StepTypeEnum
from services import git


def SaveCompileFailures(context, build, detailed_compile_failures):
  """Saves the failed build and compile failures in data store.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    detailed_compile_failures (dict): A dict of detailed compile failures.
     {
      'step_name': {
        'failures': {
          frozenset(['target1', 'target2']): {
            'rule': 'emerge',
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

  first_failures = {}
  for step_ui_name, step_info in detailed_compile_failures.iteritems():
    failures = step_info['failures']
    if not failures:
      logging.warning(
          'Cannot get detailed compile failure info for build %d,'
          ' saving step level info only.', build.id)
      first_failed_build_id = step_info.get('first_failed_build', {}).get('id')
      merged_failure_key = CompileFailure.GetMergedFailureKey(
          first_failures, first_failed_build_id, step_ui_name, frozenset([]))

      new_entity = CompileFailure.Create(
          failed_build_key=failed_build_key,
          step_ui_name=step_ui_name,
          output_targets=None,
          first_failed_build_id=first_failed_build_id,
          last_passed_build_id=step_info.get('last_passed_build', {}).get('id'),
          # Default to first_failed_build_id, will be updated later if matching
          # group exists.
          failure_group_build_id=first_failed_build_id,
          merged_failure_key=merged_failure_key)
      compile_failure_entities.append(new_entity)
      continue

    for output_targets, failure in failures.iteritems():
      first_failed_build_id = failure.get('first_failed_build', {}).get('id')
      merged_failure_key = CompileFailure.GetMergedFailureKey(
          first_failures, first_failed_build_id, step_ui_name, output_targets)

      new_entity = CompileFailure.Create(
          failed_build_key=failed_build_key,
          step_ui_name=step_ui_name,
          output_targets=list(output_targets),
          first_failed_build_id=first_failed_build_id,
          last_passed_build_id=(failure.get('last_passed_build') or
                                {}).get('id'),
          # Default to first_failed_build_id, will be updated later if matching
          # group exists.
          failure_group_build_id=first_failed_build_id,
          rule=failure.get('rule'),
          dependencies=failure.get('dependencies'),
          merged_failure_key=merged_failure_key)
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
  prev_failed_compile_steps = [
      step for step in prev_compile_steps.itervalues()
      if step.status == common_pb2.FAILURE
  ]
  prev_failures = project_api.GetCompileFailures(
      detailed_prev_build,
      prev_failed_compile_steps) if prev_failed_compile_steps else {}
  return prev_compile_steps, prev_failures


def UpdateCompileFailuresWithFirstFailureInfo(context, build,
                                              detailed_compile_failures):
  """Updates detailed_compile_failures with first failure info.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    detailed_compile_failures (dict): A dict of detailed compile failures.
      {
        'step_name': {
          'failures': {
            frozenset(['target1', 'target2']): {
              'rule': 'emerge',
              'first_failed_build': {
                'id': 8765432109,
                'number': 123,
                'commit_id': 654321
              },
              'last_passed_build': None,
            },
            ...
          },
          'first_failed_build': {
            'id': 8765432109,
            'number': 123,
            'commit_id': 654321
          },
          'last_passed_build': None,
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
      build_range=(None, build.id),
      page_size=constants.MAX_BUILDS_TO_CHECK)
  previous_builds = search_builds_response.builds

  need_go_back = False
  for prev_build in previous_builds:
    if prev_build.id == build.id:
      # TODO(crbug.com/969124): remove the check when SearchBuilds RPC works as
      # expected.
      continue

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

      step_last_passed_found = True
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
          step_last_passed_found = False
        else:
          # The failure didn't happen in the previous build, first failure found
          failure['last_passed_build'] = prev_build_info

      if step_last_passed_found:
        step_info['last_passed_build'] = prev_build_info

    if not need_go_back:
      return


def _GetEarlierBuild(build1, build2):
  if (not build1 or (build2 and build1['number'] > build2['number'])):
    return build2
  return build1


def GetFirstFailuresInCurrentBuild(context, build, detailed_compile_failures):
  """Gets failures that happened the first time in the current build.

  Failures without last_passed_build will not be included even if they failed
  the first time in current build (they have statuses other than SUCCESS or
  FAILURE in all previous builds), because Findit cannot decide the left bound
  of the regression range.

  If first failures have different last_passed_build, use the earliest one.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    detailed_compile_failures (dict): A dict of detailed compile failures.
      {
        'step_name': {
          'failures': {
            frozenset(['target1', 'target2']): {
              'rule': 'emerge',
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
  Returns:
    dict: A dict for failures that happened the first time in current build.
    {
      'failures': {
        'compile': {
          'output_targets': ['target4', 'target1', 'target2'],
          'last_passed_build': {
            'id': 8765432109,
            'number': 122,
            'commit_id': 'git_sha1'
          },
        },
      },
      'last_passed_build': {
        # In this build all the failures that happened in the build being
        # analyzed passed.
        'id': 8765432108,
        'number': 121,
        'commit_id': 'git_sha0'
      }
    }
  """
  luci_project = context.luci_project_name
  project_api = projects.GetProjectAPI(luci_project)
  assert project_api, 'Unsupported project {}'.format(luci_project)

  first_failures_in_current_build = {'failures': {}, 'last_passed_build': None}
  for step_ui_name, step_info in detailed_compile_failures.iteritems():
    if not step_info[
        'failures'] and step_info['first_failed_build']['id'] != build.id:
      # Only step level information and the step started to fail in previous
      # builds.
      continue

    if step_info['first_failed_build']['id'] == build.id and step_info[
        'last_passed_build']:
      # All failures in this step are first failures and last pass was found.
      first_failures_in_current_build['failures'][step_ui_name] = {
          'output_targets': [],
          'last_passed_build': step_info['last_passed_build'],
      }
      for output_targets, failure in step_info['failures'].iteritems():
        first_failures_in_current_build['failures'][step_ui_name][
            'output_targets'].append(output_targets)

      first_failures_in_current_build['last_passed_build'] = (
          _GetEarlierBuild(first_failures_in_current_build['last_passed_build'],
                           step_info['last_passed_build']))
      continue

    first_failures_in_step = {
        'output_targets': [],
        'last_passed_build': step_info['last_passed_build'],
    }
    for output_targets, failure in step_info['failures'].iteritems():
      if failure['first_failed_build']['id'] == build.id and failure[
          'last_passed_build']:
        first_failures_in_step['output_targets'].append(output_targets)
        first_failures_in_step['last_passed_build'] = (
            _GetEarlierBuild(first_failures_in_step['last_passed_build'],
                             failure['last_passed_build']))
    if first_failures_in_step['output_targets']:
      # Some failures are first time failures in current build.
      first_failures_in_current_build['failures'][
          step_ui_name] = first_failures_in_step

      first_failures_in_current_build['last_passed_build'] = (
          _GetEarlierBuild(first_failures_in_current_build['last_passed_build'],
                           first_failures_in_step['last_passed_build']))

  return first_failures_in_current_build


def _GetFailuresWithoutMatchingCompileFailureGroups(
    current_build_id, first_failures_in_current_build,
    failures_with_existing_group):
  """Regenerates first_failures_in_current_build without any failures with
    existing group.

  Args:
    current_build_id (int): Id of the current build that's being analyzed.
    first_failures_in_current_build (dict): A dict for failures that happened
      the first time in current build.
      {
        'failures': {
          'step name': {
            'output_targets': [
              frozenset(['target4']),
              frozenset(['target1', 'target2'])],
            'last_passed_build': {
              'id': 8765432109,
              'number': 122,
              'commit_id': 'git_sha1'
            },
          },
        },
        'last_passed_build': {
          'id': 8765432109,
          'number': 122,
          'commit_id': 'git_sha1'
        }
      }
    failures_with_existing_group (dict): Failures with their failure group id.
      {
        'step name': {
          frozenset(['target4']):  8765432000,
        ]
      }

  Returns:
    failures_without_existing_group (dict): updated version of
      first_failures_in_current_build, no failures with existing group.
  """
  failures_without_existing_group = {'failures': {}, 'last_passed_build': None}

  # Uses current_build's id as the failure group id for all the failures
  # without existing groups.
  for step_ui_name, step_failure in first_failures_in_current_build[
      'failures'].iteritems():
    step_failures_without_existing_group = []
    for output_target in step_failure['output_targets']:
      if (output_target in failures_with_existing_group.get(step_ui_name, {})
          and failures_with_existing_group[step_ui_name][output_target] !=
          current_build_id):
        # Failure is grouped into another failure.
        continue
      step_failures_without_existing_group.append(output_target)
    if step_failures_without_existing_group:
      failures_without_existing_group['failures'][step_ui_name] = {
          'output_targets': step_failures_without_existing_group,
          'last_passed_build': step_failure['last_passed_build']
      }
      failures_without_existing_group['last_passed_build'] = (
          _GetEarlierBuild(first_failures_in_current_build['last_passed_build'],
                           step_failure['last_passed_build']))
  return failures_without_existing_group


def _GetCompileFailureEntitiesForABuild(build):
  build_entity = luci_build.LuciFailedBuild.get_by_id(build.id)
  assert build_entity, 'No LuciFailedBuild entity for build {}'.format(build.id)

  compile_failure_entities = CompileFailure.query(
      ancestor=build_entity.key).fetch()
  assert compile_failure_entities, (
      'No compile failure saved in datastore for build {}'.format(build.id))
  return compile_failure_entities


def _UpdateCompileFailureEntitiesWithGroupInfo(build,
                                               failures_with_existing_group):
  """Update failure_group_build_id for failures that found matching group.

  Args:
    build (buildbucket build.proto): ALL info about the build.
    failures_with_existing_group (dict): A dict of failures from
        first_failures_in_current_build that found a matching group.
        {
          'step name': {
            frozenset(['target4']):  8765432000,
          ]
        }
  """
  compile_failure_entities = _GetCompileFailureEntitiesForABuild(build)
  entities_to_save = []
  group_failures = {}
  for failure_entity in compile_failure_entities:
    failure_group_build_id = failures_with_existing_group.get(
        failure_entity.step_ui_name,
        {}).get(failure_entity.GetFailureIdentifier())
    if failure_group_build_id:
      merged_failure_key = CompileFailure.GetMergedFailureKey(
          group_failures, failure_group_build_id, failure_entity.step_ui_name,
          failure_entity.GetFailureIdentifier())
      failure_entity.failure_group_build_id = failure_group_build_id
      failure_entity.merged_failure_key = merged_failure_key
      entities_to_save.append(failure_entity)

  ndb.put_multi(entities_to_save)


def GetFirstFailuresInCurrentBuildWithoutGroup(context, build,
                                               first_failures_in_current_build):
  """Gets first failures without existing failure groups.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    first_failures_in_current_build (dict): A dict for failures that happened
      the first time in current build.
      {
        'failures': {
          'step name': {
            'output_targets': [
              frozenset(['target4']),
              frozenset(['target1', 'target2'])],
            'last_passed_build': {
              'id': 8765432109,
              'number': 122,
              'commit_id': 'git_sha1'
            },
          },
        },
        'last_passed_build': {
          'id': 8765432109,
          'number': 122,
          'commit_id': 'git_sha1'
        }
      }

  Returns:
    failures_without_existing_group (dict): updated version of
      first_failures_in_current_build, no failures with existing group.
  """
  luci_project = context.luci_project_name
  project_api = projects.GetProjectAPI(luci_project)
  assert project_api, 'Unsupported project {}'.format(luci_project)

  failures_with_existing_group = (
      project_api.GetFailuresWithMatchingCompileFailureGroups(
          context, build, first_failures_in_current_build))

  if not failures_with_existing_group:
    # All failures need a new group.
    return first_failures_in_current_build

  _UpdateCompileFailureEntitiesWithGroupInfo(build,
                                             failures_with_existing_group)

  return _GetFailuresWithoutMatchingCompileFailureGroups(
      build.id, first_failures_in_current_build, failures_with_existing_group)


def _CreateAndSaveFailureGroupEntity(
    context, build, compile_failure_keys, last_passed_gitiles_id,
    last_passed_commit_position, first_failed_commit_position):
  group_entity = CompileFailureGroup.Create(
      luci_project=context.luci_project_name,
      luci_bucket=build.builder.bucket,
      build_id=build.id,
      gitiles_host=context.gitiles_host,
      gitiles_project=context.gitiles_project,
      gitiles_ref=context.gitiles_ref,
      last_passed_gitiles_id=last_passed_gitiles_id,
      last_passed_commit_position=last_passed_commit_position,
      first_failed_gitiles_id=context.gitiles_id,
      first_failed_commit_position=first_failed_commit_position,
      compile_failure_keys=compile_failure_keys)
  group_entity.put()


def _GetCompileFailureKeys(build, failures_without_existing_group):
  """Gets keys to the compile failures that failed the first time in the build.

  Args:
    build (buildbucket build.proto): ALL info about the build.
    failures_without_existing_group (dict): A dict for failures that happened
      the first time in current build and with no matching group.
      {
      'failures': {
        'compile': {
          'output_targets': ['target4', 'target1', 'target2'],
          'last_passed_build': {
            'id': 8765432109,
            'number': 122,
            'commit_id': 'git_sha1'
          },
        },
      },
      'last_passed_build': {
        'id': 8765432109,
        'number': 122,
        'commit_id': 'git_sha1'
      }
    }
  """
  compile_failure_entities = _GetCompileFailureEntitiesForABuild(build)

  first_failures = {
      s: failure['output_targets']
      for s, failure in failures_without_existing_group['failures'].iteritems()
  }
  compile_failure_keys = []
  for compile_failure_entity in compile_failure_entities:
    if not first_failures.get(compile_failure_entity.step_ui_name):
      continue

    if not (set(compile_failure_entity.output_targets) in first_failures[
        compile_failure_entity.step_ui_name]):
      continue
    compile_failure_keys.append(compile_failure_entity.key)
  return compile_failure_keys


def SaveCompileAnalysis(context, build, failures_without_existing_group,
                        should_group_failures):
  """Creates and saves CompileFailureAnalysis entity for the build being
    analyzed if there are first failures in the build.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    failures_without_existing_group (dict): A dict for failures that happened
      the first time in current build and with no matching group.
      {
        'failures': {
          'compile': {
            'output_targets': ['target4', 'target1', 'target2'],
            'last_passed_build': {
              'id': 8765432109,
              'number': 122,
              'commit_id': 'git_sha1'
            },
          },
        },
        'last_passed_build': {
          'id': 8765432109,
          'number': 122,
          'commit_id': 'git_sha1'
        }
      }
    should_group_failures (bool): Project config for if failures should be
      grouped to reduce duplicated analyses.
  """
  luci_project = context.luci_project_name
  project_api = projects.GetProjectAPI(luci_project)
  assert project_api, 'Unsupported project {}'.format(luci_project)

  rerun_builder_id = project_api.GetRerunBuilderId(build)

  # Gets keys to the compile failures that failed the first time in the build.
  # They will be the failures to analyze in the analysis.
  compile_failure_keys = _GetCompileFailureKeys(
      build, failures_without_existing_group)

  repo_url = git.GetRepoUrlFromContext(context)
  last_passed_gitiles_id = failures_without_existing_group['last_passed_build'][
      'commit_id']
  last_passed_commit_position = git.GetCommitPositionFromRevision(
      last_passed_gitiles_id, repo_url, ref=context.gitiles_ref)
  first_failed_commit_position = git.GetCommitPositionFromRevision(
      context.gitiles_id, repo_url, ref=context.gitiles_ref)

  if should_group_failures:
    _CreateAndSaveFailureGroupEntity(
        context, build, compile_failure_keys, last_passed_gitiles_id,
        last_passed_commit_position, first_failed_commit_position)

  analysis = CompileFailureAnalysis.Create(
      luci_project=luci_project,
      luci_bucket=build.builder.bucket,
      luci_builder=build.builder.builder,
      build_id=build.id,
      gitiles_host=context.gitiles_host,
      gitiles_project=context.gitiles_project,
      gitiles_ref=context.gitiles_ref,
      last_passed_gitiles_id=last_passed_gitiles_id,
      last_passed_commit_position=last_passed_commit_position,
      first_failed_gitiles_id=context.gitiles_id,
      first_failed_commit_position=first_failed_commit_position,
      rerun_builder_id=rerun_builder_id,
      compile_failure_keys=compile_failure_keys)
  analysis.Save()
  return analysis
