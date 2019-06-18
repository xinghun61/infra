# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the APIs that each supported project must implement."""


class ProjectAPI(object):  # pragma: no cover.

  def ClassifyStepType(self, build, step):
    """ Returns the failure type of the given build step.

    Args:
      build (buildbucket build.proto): ALL info about the build.
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
              'failure_group_build': None,
            },
            ...
          },
          'first_failed_build': {
            'id': 8765432109,
            'number': 123,
            'commit_id': 654321
          },
          'last_passed_build': None
          'failure_group_build': None,
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

  def GetFailuresWithMatchingCompileFailureGroups(
      self, context, build, first_failures_in_current_build):
    """Gets reusable failure groups for given compile failure(s).

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
      build (buildbucket build.proto): ALL info about the build.
      first_failures_in_current_build (dict): A dict for failures that happened
      the first time in current build.
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
    # For projects that don't need to group failures (e.g. chromium), this is
    # a no-op.
    # pylint: disable=unused-argument
    return {}
