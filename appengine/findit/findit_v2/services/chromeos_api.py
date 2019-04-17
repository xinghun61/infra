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
