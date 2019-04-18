# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from buildbucket_proto import common_pb2

from findit_v2.services import projects
from findit_v2.services.failure_type import StepTypeEnum


def OnBuildFailure(context, build):
  """Processes the failed build within the given context.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.

  Returns:
    True if the failed build is supported and analyzed; otherwise False.
  """
  logging.info('Context of analysis: %r', context)
  logging.info('Failed build is: %r', build.id)

  failed_steps = []
  project_api = projects.GetProjectAPI(context.luci_project_name)
  assert project_api, 'Unsupported project {}'.format(context.luci_project_name)

  for step in build.steps:
    if step.status != common_pb2.FAILURE:
      continue
    failure_type = project_api.ClassifyStepType(step)
    failed_steps.append((step, failure_type))

  if not failed_steps:
    return False

  compile_steps = [
      fs[0] for fs in failed_steps if fs[1] == StepTypeEnum.COMPILE
  ]
  if compile_steps:
    # Findit v2 is not ready yet. Logs the failure but not start an analysis.
    # TODO(crbug.com/938143): Revert change
    # https://chromium-review.googlesource.com/c/infra/infra/+/1572449
    # when Findit v2 for ChromeOS compile failure analysis is ready.
    logging.info('Compile failure found in build %d.', build.id)
    return True

  logging.info('Unsupported failure types: %r', [fs[1] for fs in failed_steps])
  return False
