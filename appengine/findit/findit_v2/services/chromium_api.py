# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the chromium-specific APIs required by Findit."""

from findit_v2.services.failure_type import StepTypeEnum
from findit_v2.services.project_api import ProjectAPI


class ChromiumProjectAPI(ProjectAPI):

  def ClassifyStepType(self, _build, step):
    """ Returns the failure type of the given build step.

    Args:
      _build (buildbucket build.proto): ALL info about the build. Itis added to
        make the signature compatible with other project, but not used here.
      step (buildbucket step.proto): ALL info about the build step.
    """
    if step.name == 'compile':
      return StepTypeEnum.COMPILE

    for log in step.logs:
      if log.name == 'step_metadata':
        return StepTypeEnum.TEST

    return StepTypeEnum.INFRA

  def GetCompileFailures(self, build, compile_steps):  # pragma: no cover.
    """Returns the detailed compile failures from a failed build.

    Args:
      build (buildbucket build.proto): ALL info about the build.
      compile_steps (buildbucket step.proto): The failed compile steps.

    Returns:
      (dict): Information about detailed compile failures.
      {
        'install packages': {
          'failures': {
            'pkg': {
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
    raise NotImplementedError

  def GetRerunBuilderId(self, build):  # pragma: no cover.
    """Gets builder id to run the rerun builds.

    Args:
      build (buildbucket build.proto): ALL info about the build.

    Returns:
      (str): Builder id in the format luci_project/luci_bucket/luci_builder
    """
    raise NotImplementedError
