# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from dto import swarming_task_error
from dto.swarming_task_error import SwarmingTaskError
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from services.flake_failure import run_swarming_util
from waterfall.test import wf_testcase


class RunSwarmingUtilTest(wf_testcase.WaterfallTestCase):

  def testCalculateNumberOfIterationsToRunWithinTimeout(self):
    self.assertEqual(
        30,
        run_swarming_util._CalculateNumberOfIterationsToRunWithinTimeout(120))

  def testEstimateSwarmingIterationTimeoutWithDataPoints(self):
    commit_position = 1000

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            commit_position=1000,
            elapsed_seconds=120,
            iterations=30,
            pass_rate=0.3)
    ]
    analysis.Save()
    self.assertEqual(
        8,
        run_swarming_util._EstimateSwarmingIterationTimeout(
            analysis, commit_position))

  def testEstimateSwarmingIterationTimeoutNoDataPoints(self):
    commit_position = 1000
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()
    self.assertEqual(
        120,
        run_swarming_util._EstimateSwarmingIterationTimeout(
            analysis, commit_position))

  def testEstimateSwarmingIterationTimeoutWithDataPointsError(self):
    commit_position = 1000

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1000, elapsed_seconds=0, iterations=0)
    ]
    analysis.Save()
    self.assertEqual(
        120,
        run_swarming_util._EstimateSwarmingIterationTimeout(
            analysis, commit_position))

  def testEstimateTimeoutForTask(self):
    self.assertEqual(3600, run_swarming_util._EstimateTimeoutForTask(1, 1))
    self.assertEqual(7200, run_swarming_util._EstimateTimeoutForTask(60, 120))

  def testGetMaximumIterationsPerSwarmingTask(self):
    self.assertEqual(1,
                     run_swarming_util._GetMaximumIterationsPerSwarmingTask(1))
    self.assertEqual(
        200, run_swarming_util._GetMaximumIterationsPerSwarmingTask(300))

  def testCalculateRunParametersForSwarmingTaskDefault(self):
    commit_position = 1000
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    self.assertEqual((30, 3600),
                     run_swarming_util.CalculateRunParametersForSwarmingTask(
                         analysis, commit_position, None))

  def testCalculateRunParametersForSwarmingTaskWithError(self):
    expected_iterations_to_run_after_timeout = 10
    commit_position = 1000
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            commit_position=1000,
            pass_rate=1,
            iterations=1,
            elapsed_seconds=400)
    ]
    analysis.Save()

    self.assertEqual((expected_iterations_to_run_after_timeout, 3600),
                     run_swarming_util.CalculateRunParametersForSwarmingTask(
                         analysis, commit_position,
                         SwarmingTaskError(
                             code=swarming_task_error.TIMED_OUT, message='m')))

  def testCalculateRunParametersForSwarmingTaskExceedsMaxTasks(self):
    commit_position = 1000
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            commit_position=commit_position,
            iterations=100,
            elapsed_seconds=100,
            pass_rate=1)
    ]
    analysis.Save()

    self.assertEqual((200, 3600),
                     run_swarming_util.CalculateRunParametersForSwarmingTask(
                         analysis, commit_position, None))

  def testReportSwarmingTaskErrorNoError(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.start_time = datetime(2018, 1, 23, 1, 0, 0)
    analysis.end_time = datetime(2018, 1, 23, 1, 1, 0)
    analysis.Save()
    run_swarming_util.ReportSwarmingTaskError(analysis, None)

    self.assertIsNone(analysis.error)

  def testReportSwarmingTaskError(self):
    error_code = 1
    error_message = 'e'

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.start_time = datetime(2018, 1, 23, 1, 0, 0)
    analysis.end_time = datetime(2018, 1, 23, 1, 1, 0)
    analysis.Save()
    run_swarming_util.ReportSwarmingTaskError(
        analysis, SwarmingTaskError(code=error_code, message=error_message))

    self.assertEqual(error_code, analysis.error['code'])
    self.assertEqual(error_message, analysis.error['message'])
