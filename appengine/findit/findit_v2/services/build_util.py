# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for logic to process a buildbucket build."""

from buildbucket_proto import common_pb2

from findit_v2.services import projects
from findit_v2.services.constants import ANALYZED_BUILD_ID_TAG_KEY


def GetFailedStepsInBuild(context, build):
  """Gets failed steps and their types for a LUCI build.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.

  Returns:
    A list of tuples, each tuple contains the information of a failed step and
    its type.
  """
  project_api = projects.GetProjectAPI(context.luci_project_name)

  failed_steps = []
  for step in build.steps:
    if step.status != common_pb2.FAILURE:
      continue
    failure_type = project_api.ClassifyStepType(build, step)
    failed_steps.append((step, failure_type))

  return failed_steps


def GetAnalyzedBuildIdFromRerunBuild(build):
  """Gets analyzed build id from rerun_build's tag, otherwise None.

  Args:
    rerun_build (buildbucket build.proto): ALL info about the build.

  Returns:
    int: build_id of the analyzed build.
  """
  for tag in build.tags:
    if tag.key == ANALYZED_BUILD_ID_TAG_KEY:
      return int(tag.value)
  return None
