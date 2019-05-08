# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from buildbucket_proto import common_pb2

from findit_v2.model.compile_failure import CompileFailureAnalysis
from findit_v2.model.compile_failure import CompileRerunBuild
from findit_v2.services import build_util
from findit_v2.services import projects
from findit_v2.services.analysis.compile_failure import (
    compile_failure_rerun_analysis)
from findit_v2.services.analysis.compile_failure import pre_compile_analysis
from findit_v2.services.failure_type import StepTypeEnum


def AnalyzeCompileFailure(context, build, compile_steps):
  """Analyzes compile failure from a failed ci/postsubmit build.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    compile_steps (list of buildbucket step.proto): The failed compile steps.

  Returns:
    (bool): Returns True if a new analysis starts, otherwise False.
  """
  if context.luci_project_name == 'chromium':
    logging.warning('Findit does not support chromium project in v2.')
    return False

  project_api = projects.GetProjectAPI(context.luci_project_name)
  if not project_api:
    logging.debug('Unsupported project %s', context.luci_project_name)
    return False

  detailed_compile_failures = project_api.GetCompileFailures(
      build, compile_steps)
  # Checks previous builds to look for first time failures for all the failures
  # in current failed build.
  pre_compile_analysis.UpdateCompileFailuresWithFirstFailureInfo(
      context, build, detailed_compile_failures)
  # TODO(crbug.com/949836): Look for existing failure groups.
  pre_compile_analysis.SaveCompileFailures(context, build,
                                           detailed_compile_failures)

  # Looks for the failures that started to fail in the current build.
  first_failures_in_current_build = (
      pre_compile_analysis.GetFirstFailuresInCurrentBuild(
          context, build, detailed_compile_failures))
  if not first_failures_in_current_build['failures']:
    # No first time failures in current build. No need for a new analysis.
    return False

  # Start a new analysis to analyze the first time failures.
  pre_compile_analysis.SaveCompileAnalysis(context, build,
                                           first_failures_in_current_build)
  compile_failure_rerun_analysis.RerunBasedAnalysis(context, build.id, build)
  return True


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
  assert project_api, 'Unsupported project %s.' % context.luci_project_name

  analysis = CompileFailureAnalysis.GetVersion(analyzed_build_id)
  if not analysis:
    logging.error('CompileFailureAnalysis missing for %d.', analyzed_build_id)
    return False

  rerun_build_entity = CompileRerunBuild.get_by_id(
      rerun_build.id, parent=analysis.key)
  if not rerun_build_entity:
    logging.error('CompileRerunBuild entity for build %d missing.',
                  rerun_build.id)
    return False

  detailed_compile_failures = {}
  if rerun_build.status == common_pb2.FAILURE:
    failed_steps = build_util.GetFailedStepsInBuild(context, rerun_build)
    compile_steps = [
        fs[0] for fs in failed_steps if fs[1] == StepTypeEnum.COMPILE
    ]
    detailed_compile_failures = project_api.GetCompileFailures(
        rerun_build, compile_steps) if compile_steps else {}

  rerun_build_entity.SaveRerunBuildResults(rerun_build.status,
                                           detailed_compile_failures)
  return True


def OnCompileRerunBuildCompletion(context, rerun_build):
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

  compile_failure_rerun_analysis.RerunBasedAnalysis(context, analyzed_build_id,
                                                    rerun_build)
  return True
