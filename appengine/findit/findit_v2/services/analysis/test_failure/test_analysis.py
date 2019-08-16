# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from buildbucket_proto import common_pb2

from findit_v2.model.test_failure import TestFailureAnalysis
from findit_v2.model.test_failure import TestFailureInRerunBuild
from findit_v2.model.test_failure import TestRerunBuild
from findit_v2.services import build_util
from findit_v2.services import projects
from findit_v2.services.analysis.test_failure.test_analysis_api import (
    TestAnalysisAPI)
from findit_v2.services.failure_type import StepTypeEnum

# Placeholder to ack as a test_failure in a failed step, if in fact there's no
# test level failure info for that step.
_TEST_FAILURE_PLACEHOLDER = {frozenset([]): {}}


def AnalyzeTestFailure(context, build, test_steps):
  """Analyzes test failure from a failed ci/postsubmit build.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    test_steps (list of buildbucket step.proto): The failed test steps.

  Returns:
    (bool): Returns True if a new analysis starts, otherwise False.
  """
  luci_project = context.luci_project_name
  if luci_project == 'chromium':
    logging.warning('Findit does not support chromium project in v2.')
    return False

  project_api = projects.GetProjectAPI(luci_project)

  analysis_api = TestAnalysisAPI()

  # Project config for if failures should be grouped to reduce duplicated
  # analyses.
  should_group_failures = projects.PROJECT_CFG.get(
      luci_project, {}).get('should_group_failures')

  detailed_test_failures = project_api.GetTestFailures(build, test_steps)
  # Checks previous builds to look for first time failures for all the failures
  # in current failed build.
  analysis_api.UpdateFailuresWithFirstFailureInfo(context, build,
                                                  detailed_test_failures)
  analysis_api.SaveFailures(context, build, detailed_test_failures)

  # Looks for the failures that started to fail in the current build.
  first_failures_in_current_build = (
      analysis_api.GetFirstFailuresInCurrentBuild(build,
                                                  detailed_test_failures))
  if not first_failures_in_current_build.get('failures'):
    logging.info(
        'No new analysis for build %d because all failures have '
        'happened in previous builds.', build.id)
    return False

  # Filters out the first failures with existing failure group.
  if should_group_failures:
    failures_without_existing_group = (
        analysis_api.GetFirstFailuresInCurrentBuildWithoutGroup(
            project_api, context, build, first_failures_in_current_build))
  else:
    failures_without_existing_group = first_failures_in_current_build

  if not failures_without_existing_group.get('failures'):
    logging.info(
        'All failures have matching failure groups in build %s,'
        ' no need to start a new analysis.', build.id)
    return False

  # Start a new analysis to analyze the first time failures.
  analysis_api.SaveFailureAnalysis(project_api, context, build,
                                   failures_without_existing_group,
                                   should_group_failures)
  analysis_api.RerunBasedAnalysis(context, build.id)
  return True


def _SaveRerunBuildResults(rerun_build_entity, status, detailed_test_failures):
  """Saves the results of the rerun build.

  Args:
    status (int): status of the build. See common_pb2 for available values.
    detailed_test_failures (dict): Test failures in the rerun build.
    Format is like:
    {
      'step_name': {
        'failures': {
          frozenset(['test1']): {
            'first_failed_build': {
              'id': 8765432109,
              'number': 123,
              'commit_id': 654321
            },
            'last_passed_build': None,
            'properties': {
              # Arbitrary information about the failure if exists.
            }
          },
        'first_failed_build': {
          'id': 8765432109,
          'number': 123,
          'commit_id': 654321
        },
        'last_passed_build': None,
        'properties': {
          # Arbitrary information about the failure if exists.
        }
      },
    }
  """
  rerun_build_entity.status = status
  rerun_build_entity.failures = []
  for step_ui_name, step_info in detailed_test_failures.iteritems():
    for test_set in step_info['failures'] or _TEST_FAILURE_PLACEHOLDER:
      failure_entity = TestFailureInRerunBuild(
          step_ui_name=step_ui_name,
          test=next(iter(test_set)) if test_set else None)
      rerun_build_entity.failures.append(failure_entity)
  rerun_build_entity.put()


def _ProcessAndSaveRerunBuildResult(context, analyzed_build_id, rerun_build):
  """Gets results of a completed rerun build and save it in datastore.

  Args:
     context (findit_v2.services.context.Context): Scope of the analysis.
     analyzed_build_id (int): Id of the failed ci/post_submit build that's being
       analyzed.
     rerun_build (buildbucket build.proto): ALL info about the rerun build.

   Returns:
     True if the rerun build entity is updated, otherwise False.
  """
  project_api = projects.GetProjectAPI(context.luci_project_name)

  analysis = TestFailureAnalysis.GetVersion(analyzed_build_id)
  if not analysis:
    logging.error('TestFailureAnalysis missing for %d.', analyzed_build_id)
    return False

  rerun_build_entity = TestRerunBuild.get_by_id(
      rerun_build.id, parent=analysis.key)
  if not rerun_build_entity:
    logging.error('TestRerunBuild entity for build %d missing.', rerun_build.id)
    return False

  detailed_test_failures = {}
  if rerun_build.status == common_pb2.FAILURE:
    failed_steps = build_util.GetFailedStepsInBuild(context, rerun_build)
    test_steps = [fs[0] for fs in failed_steps if fs[1] == StepTypeEnum.TEST]
    detailed_test_failures = project_api.GetTestFailures(
        rerun_build, test_steps) if test_steps else {}
  _SaveRerunBuildResults(rerun_build_entity, rerun_build.status,
                         detailed_test_failures)
  return True


def OnTestRerunBuildCompletion(context, rerun_build):
  """Processes the completed rerun build then continues the analysis.

  Processes and stores results of the completed rerun build. And then resume the
  analysis to either start the next rerun build or identify the culprit.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    rerun_build (buildbucket build.proto): ALL info about the rerun build.

  Returns:
    True if the rerun build entity is updated, otherwise False.
  """
  analyzed_build_id = build_util.GetAnalyzedBuildIdFromRerunBuild(rerun_build)
  if not analyzed_build_id:
    logging.error('analyzed_build_id not set in the rerun build %d.',
                  rerun_build.id)
    return False

  build_saved = _ProcessAndSaveRerunBuildResult(context, analyzed_build_id,
                                                rerun_build)
  if not build_saved:
    return False

  TestAnalysisAPI().RerunBasedAnalysis(context, analyzed_build_id)
  return True
