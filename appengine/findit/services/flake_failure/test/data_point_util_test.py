# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from model.flake.master_flake_analysis import DataPoint
from services.flake_failure import data_point_util
from waterfall.flake import flake_constants
from waterfall.test import wf_testcase


class DataPointUtilTest(wf_testcase.WaterfallTestCase):

  def testGetMaximumIterationsToRunPerDataPoint(self):
    self.assertEqual(flake_constants.DEFAULT_MAX_ITERATIONS_TO_RERUN,
                     data_point_util.GetMaximumIterationsToRunPerDataPoint())

  def testGetMaximumSwarmingTaskRetriesPerDataPoint(self):
    self.assertEqual(
        flake_constants.DEFAULT_MAX_SWARMING_TASK_RETRIES_PER_DATA_POINT,
        data_point_util.GetMaximumSwarmingTaskRetriesPerDataPoint())

  @mock.patch.object(
      data_point_util,
      'GetMaximumSwarmingTaskRetriesPerDataPoint',
      return_value=3)
  def testMaximumSwarmingTaskRetriesReached(self, _):
    data_point = DataPoint.Create(failed_swarming_task_attempts=4)
    self.assertTrue(
        data_point_util.MaximumSwarmingTaskRetriesReached(data_point))

  @mock.patch.object(
      data_point_util,
      'GetMaximumIterationsToRunPerDataPoint',
      return_value=100)
  def testMaximumIterationsPerDataPointReached(self, _):
    self.assertTrue(data_point_util.MaximumIterationsPerDataPointReached(150))

  def testUpdateFailedSwarmingTaskAttempts(self):
    data_point = DataPoint.Create(failed_swarming_task_attempts=1)
    data_point_util.UpdateFailedSwarmingTaskAttempts(data_point)
    self.assertEqual(2, data_point.failed_swarming_task_attempts)
