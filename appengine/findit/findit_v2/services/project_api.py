# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the APIs that each supported project must implement."""


class ProjectAPI(object):  # pragma: no cover.

  def ClassifyStepType(self, step):
    """ Returns the failure type of the given build step.

    Args:
      step (buildbucket step.proto): ALL info about the build step.

    Returns:
      findit_v2.services.failure_type.StepTypeEnum
    """
    # pylint: disable=unused-argument
    raise NotImplementedError

  def GetCompileFailures(self, build, compile_steps):
    """Returns the detailed compile failures from a failed build.

    Args:
      build (buildbucket build.proto): ALL info about the build.
      compile_steps (buildbucket step.proto): The failed compile steps.

    Returns:
      (dict): Information about detailed compile_failures.
      {
        'build_packages': {
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
    # pylint: disable=unused-argument
    raise NotImplementedError

  def GetRerunBuilderId(self, build):
    """Gets builder id to run the rerun builds.

    Args:
      build (buildbucket build.proto): ALL info about the build.

    Returns:
      (str): Builder id in the format luci_project/luci_bucket/luci_builder
    """
    # pylint: disable=unused-argument
    raise NotImplementedError

  def GetCompileRerunBuildInputProperties(self, referred_build, failed_targets):
    """Gets input properties of a rerun build for compile failures.

    Args:
      referred_build (buildbucket build.proto): ALL info about the
        referred_build. This build could be the build being analyzed, or a
        previous rerun build for the failed build.
      failed_targets (list of str): Targets Findit wants to rerun in the build.

    Returns:
      (dict): input properties of the rerun build."""
    # pylint: disable=unused-argument
    return NotImplementedError
