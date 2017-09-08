# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
import copy
import mock

from model.flake.master_flake_analysis import DataPoint
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis

from waterfall.flake import flake_analysis_util
from waterfall.flake import flake_constants
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class FlakeAnalysisUtilTest(wf_testcase.WaterfallTestCase):

  def testUpdateIterationsToRerunNoIterationsToUpdate(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.Save()

    flake_analysis_util.UpdateIterationsToRerun(analysis, None)
    self.assertEqual(analysis.algorithm_parameters,
                     DEFAULT_CONFIG_DATA['check_flake_settings'])

  def testUpdateIterationsToRerun(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.Save()

    iterations_to_rerun = 100

    flake_analysis_util.UpdateIterationsToRerun(analysis, iterations_to_rerun)
    self.assertEqual(
        analysis.algorithm_parameters['swarming_rerun']['iterations_to_rerun'],
        iterations_to_rerun)
    self.assertEqual(
        analysis.algorithm_parameters['try_job_rerun']['iterations_to_rerun'],
        iterations_to_rerun)

  def testGetIterationsToRerun(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.algorithm_parameters = {
        'swarming_rerun': {
            'iterations_to_rerun': 1
        }
    }
    self.assertEqual(1, flake_analysis_util.GetIterationsToRerun(
        None, analysis))
    self.assertEqual(2, flake_analysis_util.GetIterationsToRerun(2, analysis))

  def testNormalizeDataPoints(self):
    data_points = [
        DataPoint.Create(pass_rate=0.9, build_number=2),
        DataPoint.Create(pass_rate=0.8, build_number=1),
        DataPoint.Create(pass_rate=1.0, build_number=3)
    ]
    normalized_data_points = (
        flake_analysis_util.NormalizeDataPointsByBuildNumber(data_points))
    self.assertEqual(normalized_data_points[0].run_point_number, 3)
    self.assertEqual(normalized_data_points[1].run_point_number, 2)
    self.assertEqual(normalized_data_points[2].run_point_number, 1)
    self.assertEqual(normalized_data_points[0].pass_rate, 1.0)
    self.assertEqual(normalized_data_points[1].pass_rate, 0.9)
    self.assertEqual(normalized_data_points[2].pass_rate, 0.8)

  def testEstimateSwarmingIterationTimeoutWithAnalysisWithNoDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    timeout = flake_analysis_util.EstimateSwarmingIterationTimeout(analysis)

    self.assertEqual(timeout, 120)

  def testCalculateNumberOfIterationsToRunWithinTimeout(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    iterations = 60
    timeout_per_test = 60
    self.assertEqual(
        flake_analysis_util.CalculateNumberOfIterationsToRunWithinTimeout(
            analysis, iterations, timeout_per_test), 60)

  def testCalculateNumberOfIterationsToRunWithinTimeoutWithZero(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    iterations = 60
    timeout_per_test = 10000
    self.assertEqual(
        flake_analysis_util.CalculateNumberOfIterationsToRunWithinTimeout(
            analysis, iterations, timeout_per_test), 1)

  def testEstimateSwarmingIterationTimeoutWithAnalysisLessDataPoints(self):
    flake_task = FlakeSwarmingTask.Create('m', 'b', 100, 's', 't')
    flake_task.tries = 10
    flake_task.started_time = datetime(1, 1, 1, 0, 0, 0)
    flake_task.completed_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.put()

    flake_task = FlakeSwarmingTask.Create('m', 'b', 101, 's', 't')
    flake_task.tries = 20
    flake_task.started_time = datetime(1, 1, 1, 0, 0, 0)
    flake_task.completed_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])

    analysis.data_points = [
        DataPoint.Create(build_number=100, iterations=10),
        DataPoint.Create(build_number=101, iterations=20)
    ]
    analysis.put()

    try:
      previous_cushion = flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = 1
      timeout = flake_analysis_util.EstimateSwarmingIterationTimeout(analysis)
    finally:
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = previous_cushion

    self.assertEqual(240, timeout)

  def testEstimateSwarmingIterationTimeoutWithDefaultTimeout(self):
    flake_task = FlakeSwarmingTask.Create('m', 'b', 100, 's', 't')
    flake_task.tries = 10
    flake_task.started_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.completed_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])

    analysis.data_points = [
        DataPoint.Create(build_number=100, iterations=10),
    ]
    analysis.put()

    try:
      previous_cushion = flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = 1
      timeout = flake_analysis_util.EstimateSwarmingIterationTimeout(analysis)
    finally:
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = previous_cushion

    self.assertEqual(120, timeout)

  def testEstimateSwarmingIterationTimeoutCullNoneIterations(self):
    flake_task = FlakeSwarmingTask.Create('m', 'b', 101, 's', 't')
    flake_task.tries = 20
    flake_task.started_time = datetime(1, 1, 1, 0, 0, 0)
    flake_task.completed_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])

    analysis.data_points = [
        DataPoint.Create(build_number=100, iterations=None),
        DataPoint.Create(build_number=101, iterations=20)
    ]
    analysis.put()

    try:
      previous_cushion = flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = 1
      timeout = flake_analysis_util.EstimateSwarmingIterationTimeout(analysis)
    finally:
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = previous_cushion

    self.assertEqual(180, timeout)

  def testEstimateSwarmingIterationTimeoutWithNoneForDataPointIterations(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])

    analysis.data_points = [
        DataPoint.Create(build_number=100, iterations=None),
    ]
    analysis.put()

    try:
      previous_cushion = flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = 1
      timeout = flake_analysis_util.EstimateSwarmingIterationTimeout(analysis)
    finally:
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = previous_cushion

    self.assertEqual(120, timeout)

  def testEstimateSwarmingIterationTimeoutWithMoreDataPointsSampleSize(self):
    flake_task = FlakeSwarmingTask.Create('m', 'b', 100, 's', 't')
    flake_task.tries = 20
    flake_task.started_time = datetime(1, 1, 1, 0, 0, 0)
    flake_task.completed_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.put()

    flake_task = FlakeSwarmingTask.Create('m', 'b', 101, 's', 't')
    flake_task.tries = 20
    flake_task.started_time = datetime(1, 1, 1, 0, 0, 0)
    flake_task.completed_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.put()

    flake_task = FlakeSwarmingTask.Create('m', 'b', 102, 's', 't')
    flake_task.tries = 20
    flake_task.started_time = datetime(1, 1, 1, 0, 0, 0)
    flake_task.completed_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.put()

    flake_task = FlakeSwarmingTask.Create('m', 'b', 103, 's', 't')
    flake_task.tries = 20
    flake_task.started_time = datetime(1, 1, 1, 0, 0, 0)
    flake_task.completed_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.put()

    flake_task = FlakeSwarmingTask.Create('m', 'b', 104, 's', 't')
    flake_task.tries = 20
    flake_task.started_time = datetime(1, 1, 1, 0, 0, 0)
    flake_task.completed_time = datetime(1, 1, 1, 1, 0, 0)
    flake_task.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(build_number=99, iterations=10),
        DataPoint.Create(build_number=100, iterations=20),
        DataPoint.Create(build_number=101, iterations=20),
        DataPoint.Create(build_number=102, iterations=20),
        DataPoint.Create(build_number=103, iterations=20),
        DataPoint.Create(build_number=104, iterations=20),
    ]  # Total should be 100 iterations.
    analysis.put()

    try:
      previous_cushion = flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = 1
      timeout = flake_analysis_util.EstimateSwarmingIterationTimeout(analysis)
    finally:
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER = previous_cushion

    # 100 iterations and 300 minutes means 3 minutes per iteration.
    self.assertEqual(180, timeout)
