# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from buildbucket_proto import common_pb2

from findit_v2.model.compile_failure import CompileFailureAnalysis
from findit_v2.model.compile_failure import CompileRerunBuild
from findit_v2.services import build_util
from findit_v2.services import projects
from findit_v2.services.failure_type import StepTypeEnum


def _ProcessAndSaveRerunBuildResult(context, rerun_build):
  """Gets results of a completed rerun build and save it in datastore.

  Args:
     context (findit_v2.services.context.Context): Scope of the analysis.
     rerun_build (buildbucket build.proto): ALL info about the rerun build.

   Returns:
     True if the rerun build entity is updated, otherwise False.
  """
  project_api = projects.GetProjectAPI(context.luci_project_name)
  assert project_api, 'Unsupported project %s.' % context.luci_project_name

  analyzed_build_id = build_util.GetAnalyzedBuildIdFromRerunBuild(rerun_build)
  if not analyzed_build_id:
    logging.error('analyzed_build_id not set in the rerun build %d.',
                  rerun_build.id)
    return False

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
  """Processes the build and continues the analysis.

  Processes and stores results of the completed rerun build. And then resume the
  analysis to either start the next rerun build or identify the culprit.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    rerun_build (buildbucket build.proto): ALL info about the rerun build.

  Returns:
    True if the rerun build entity is updated, otherwise False.
  """
  build_saved = _ProcessAndSaveRerunBuildResult(context, rerun_build)
  if not build_saved:
    return False

  # TODO: Look for culprit based on rerun builds.
  # Trigger the next rerun build.
  return True
