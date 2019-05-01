# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the chromium-specific APIs required by Findit."""

import logging

from google.protobuf import json_format

from findit_v2.services.failure_type import StepTypeEnum
from findit_v2.services.project_api import ProjectAPI

_COMPILE_STEP_NAME = 'build_packages'


class ChromeOSProjectAPI(ProjectAPI):

  def ClassifyStepType(self, step):
    """ Returns the failure type of the given build step.

    Args:
      step (buildbucket step.proto): ALL info about the build step.
    """
    if step.name == _COMPILE_STEP_NAME:
      return StepTypeEnum.COMPILE

    return StepTypeEnum.INFRA

  def GetCompileFailures(self, build, compile_steps):
    """Returns the detailed compile failures from a failed build.

    For ChromeOS builds, the failures are stored in the build's output
    property 'build_compile_failure_output'.

    Args:
      build (buildbucket build.proto): ALL info about the build.
      compile_steps (list of buildbucket step.proto): The failed compile steps.

    Returns:
      (dict): Information about detailed compile failures.
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
    # pylint: disable=unused-argument
    build_info = {
        'id': build.id,
        'number': build.number,
        'commit_id': build.input.gitiles_commit.id
    }

    detailed_compile_failures = {
        _COMPILE_STEP_NAME: {
            'failures': {},
            'first_failed_build': build_info,
            'last_passed_build': None
        }
    }

    # Convert the Struct to standard dict, to use .get, .iteritems etc.
    build_compile_failure_output = json_format.MessageToDict(
        build.output.properties).get('build_compile_failure_output')

    if not build_compile_failure_output:
      logging.debug('No build_compile_failure_output for ChromeOS build %d.',
                    build.id)
      return detailed_compile_failures

    failures_dict = detailed_compile_failures[_COMPILE_STEP_NAME]['failures']
    for failure in build_compile_failure_output.get('failures', []):
      # Joins targets in a str for faster look up when looking for the same
      # failures in previous builds.
      targets_str = ' '.join(sorted(failure['output_targets']))
      failures_dict[targets_str] = failure
      failures_dict[targets_str]['first_failed_build'] = build_info
      failures_dict[targets_str]['last_passed_build'] = None

    return detailed_compile_failures

  def GetRerunBuilderId(self, build):
    """Gets builder id to run the rerun builds.

    Args:
      build (buildbucket build.proto): ALL info about the build.

    Returns:
      (str): Builder id in the format luci_project/luci_bucket/luci_builder
    """
    rerun_builder = json_format.MessageToDict(
        build.output.properties).get('BISECT_BUILDER')

    assert rerun_builder, 'Failed to find rerun builder for build {}'.format(
        build.id)

    return '{project}/{bucket}/{builder}'.format(
        project=build.builder.project,
        bucket=build.builder.bucket,
        builder=rerun_builder)

  def GetCompileRerunBuildInputProperties(self, referred_build, failed_targets):
    """Gets input properties of a rerun build for compile failures.

    Args:
      referred_build (buildbucket build.proto): ALL info about the
        referred_build. This build could be the build being analyzed, or a
        previous rerun build for the failed build.
      failed_targets (dict): Targets Findit wants to rerun in the build.

    Returns:
      (dict): input properties of the rerun build."""
    build_target = json_format.MessageToDict(
        referred_build.input.properties).get('build_target', {}).get('name')
    assert build_target, (
        'Failed to get build_target for ChromeOS build {}'.format(
            referred_build.id))

    targets = failed_targets.get(_COMPILE_STEP_NAME, [])
    if not targets:
      return None

    return {
        'recipe': 'build_target',
        'build_target': {
            'name': build_target
        },
        'findit_bisect': {
            'targets': targets
        },
        'build_image': False
    }
