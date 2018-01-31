# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to assist in operations on DataPoint objects."""

from waterfall import waterfall_config
from waterfall.flake import flake_constants


def GetMaximumIterationsToRunPerDataPoint():
  return waterfall_config.GetCheckFlakeSettings().get(
      'max_iterations_to_rerun',
      flake_constants.DEFAULT_MAX_ITERATIONS_TO_RERUN)


def GetMaximumSwarmingTaskRetriesPerDataPoint():
  return waterfall_config.GetCheckFlakeSettings().get(
      'maximum_swarming_task_retries_per_data_point',
      flake_constants.DEFAULT_MAX_SWARMING_TASK_RETRIES_PER_DATA_POINT)


def MaximumSwarmingTaskRetriesReached(data_point):
  """Determines whether a data point has too many failed swarming task attempts.

  Args:
    data_point (DataPoint): The data point to check.

  Returns:
    True if the data point has had too many failed attempts at a swarming task.
  """
  max_swarming_retries = GetMaximumSwarmingTaskRetriesPerDataPoint()
  return data_point.failed_swarming_task_attempts > max_swarming_retries


def MaximumIterationsPerDataPointReached(iterations):
  max_iterations_to_run = GetMaximumIterationsToRunPerDataPoint()
  return iterations >= max_iterations_to_run


def UpdateFailedSwarmingTaskAttempts(data_point):
  assert data_point
  data_point.failed_swarming_task_attempts += 1
  data_point.put()
