# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common import constants
from common.pipeline_wrapper import pipeline_handlers
from model import analysis_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake import recursive_flake_pipeline
from waterfall.flake import recursive_flake_try_job_pipeline
from waterfall.flake.recursive_flake_pipeline import _GetNextBuildNumber
from waterfall.flake.recursive_flake_pipeline import NextBuildNumberPipeline
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class RecursiveFlakePipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _CreateAndSaveMasterFlakeAnalysis(
      self, master_name, builder_name, build_number, step_name,
      test_name, status):
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = status
    analysis.Save()

  def _CreateAndSaveFlakeSwarmingTask(
      self, master_name, builder_name, build_number, step_name, test_name,
      status=analysis_status.PENDING, number_of_iterations=0, error=None):
    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = status
    flake_swarming_task.tries = number_of_iterations
    flake_swarming_task.error = error
    flake_swarming_task.put()

  def _GenerateDataPoints(self, pass_rates, build_numbers):
    data_points = []
    for i in range(0, len(pass_rates)):
      data_point = DataPoint()
      data_point.pass_rate = pass_rates[i]
      data_point.build_number = build_numbers[i]
      data_points.append(data_point)
    return data_points

  def testGetETAToStartAnalysisWhenManuallyTriggered(self):
    mocked_utcnow = datetime.utcnow()
    self.MockUTCNow(mocked_utcnow)
    self.assertEqual(mocked_utcnow,
                     recursive_flake_pipeline._GetETAToStartAnalysis(True))

  def testGetETAToStartAnalysisWhenTriggeredOnPSTWeekend(self):
    # Sunday 1pm in PST, and Sunday 8pm in UTC.
    mocked_pst_now = datetime(2016, 9, 04, 13, 0, 0, 0)
    mocked_utc_now = datetime(2016, 9, 04, 20, 0, 0, 0)
    self.MockUTCNow(mocked_utc_now)
    self.MockUTCNowWithTimezone(mocked_utc_now)
    with mock.patch('libs.time_util.GetDatetimeInTimezone') as timezone_func:
      timezone_func.side_effect = [mocked_pst_now, None]
      self.assertEqual(mocked_utc_now,
                       recursive_flake_pipeline._GetETAToStartAnalysis(False))

  def testGetETAToStartAnalysisWhenTriggeredOffPeakHoursOnPSTWeekday(self):
    # Tuesday 1am in PST, and Tuesday 8am in UTC.
    mocked_pst_now = datetime(2016, 9, 20, 1, 0, 0, 0)
    mocked_utc_now = datetime(2016, 9, 20, 8, 0, 0, 0)
    self.MockUTCNow(mocked_utc_now)
    self.MockUTCNowWithTimezone(mocked_utc_now)
    with mock.patch('libs.time_util.GetDatetimeInTimezone') as timezone_func:
      timezone_func.side_effect = [mocked_pst_now, None]
      self.assertEqual(mocked_utc_now,
                       recursive_flake_pipeline._GetETAToStartAnalysis(False))

  def testGetETAToStartAnalysisWhenTriggeredInPeakHoursOnPSTWeekday(self):
    # Tuesday 1pm in PST, and Tuesday 8pm in UTC.
    seconds_delay = 10
    mocked_pst_now = datetime(2016, 9, 20, 13, 0, 0, 0)
    mocked_utc_now = datetime(2016, 9, 20, 20, 0, 0, 0)
    mocked_pst_eta = datetime(
        2016, 9, 20, 18, 0, seconds_delay, 0)  # With arbitrary delay of 10s.
    mocked_utc_eta = datetime(2016, 9, 21, 1, 0, 0, 0)  # Without delay.
    self.MockUTCNow(mocked_utc_now)
    self.MockUTCNowWithTimezone(mocked_utc_now)
    with mock.patch('libs.time_util.GetDatetimeInTimezone') as (
        timezone_func), mock.patch('random.randint') as random_func:
      timezone_func.side_effect = [mocked_pst_now, mocked_utc_eta]
      random_func.side_effect = [seconds_delay, None]
      self.assertEqual(mocked_utc_eta,
                       recursive_flake_pipeline._GetETAToStartAnalysis(False))
      self.assertEqual(2, timezone_func.call_count)
      self.assertEqual(mock.call('US/Pacific', mocked_utc_now),
                       timezone_func.call_args_list[0])
      self.assertEqual(mock.call('UTC', mocked_pst_eta),
                       timezone_func.call_args_list[1])

  def testRecursiveFlakePipeline(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    run_build_number = 100
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE
    task_id = 'task_id'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.Save()

    self.MockPipeline(
        recursive_flake_pipeline.TriggerFlakeSwarmingTaskPipeline,
        'task_id',
        expected_args=[master_name, builder_name,
                       run_build_number, step_name, [test_name]],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.ProcessFlakeSwarmingTaskResultPipeline,
        'test_result_future',
        expected_args=[master_name, builder_name,
                       run_build_number, step_name, task_id,
                       master_build_number, test_name,
                       analysis.version_number],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.NextBuildNumberPipeline,
        '',
        expected_args=[master_name, builder_name, master_build_number,
                       build_number, step_name, test_name,
                       analysis.version_number],
        expected_kwargs={'use_nearby_neighbor': False,
                         'manually_triggered': False})

    rfp = RecursiveFlakePipeline(
        master_name, builder_name, build_number, step_name, test_name,
        analysis.version_number, master_build_number,
        use_nearby_neighbor=False, step_size=0)

    rfp.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  def testNextBuildPipelineForNewRecursionFirstFlake(self, *_):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.COMPLETED
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    data_point = DataPoint()
    data_point.pass_rate = .08
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    self.MockPipeline(recursive_flake_pipeline.RecursiveFlakePipeline,
                      '',
                      expected_args=['m', 'b', 99, 's', 't', 1, 100],
                      expected_kwargs={
                          'manually_triggered': False,
                          'use_nearby_neighbor': False,
                          'step_size': 1,
                      })
    pipeline = NextBuildNumberPipeline(
        master_name, builder_name, master_build_number, build_number,
        step_name, test_name, analysis.version_number)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  @mock.patch(
      'waterfall.flake.recursive_flake_pipeline.RecursiveFlakePipeline')
  def testNextBuildPipelineForFailedSwarmingTask(self, mocked_pipeline, *_):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    swarming_task_error = {
        'code': 1,
        'message': 'some failure message',
    }
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.ERROR, error=swarming_task_error
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    self.MockPipeline(recursive_flake_pipeline.UpdateFlakeBugPipeline,
                      '',
                      expected_args=[analysis.key.urlsafe()],
                      expected_kwargs={})

    pipeline = NextBuildNumberPipeline(
        master_name, builder_name, master_build_number, build_number,
        step_name, test_name, 1)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    mocked_pipeline.assert_not_called()
    self.assertEqual(swarming_task_error, analysis.error)

  def testGetNextRunSetStableAfterFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    data_points = self._GenerateDataPoints(
        pass_rates=[0.8, 1.0], build_numbers=[100, 80])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(next_run, 79)

  def testGetNextRunFlakeAfterStable(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    data_points = self._GenerateDataPoints(
        pass_rates=[1.0, 0.8], build_numbers=[100, 80])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(next_run, 79)

  def testGetNextRunNoTestAfterStable(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    data_points = self._GenerateDataPoints(
        pass_rates=[1.0, -1], build_numbers=[100, 80])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(next_run, -1)

  def testGetNextRunFlakedOut(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    data_points = self._GenerateDataPoints(
        pass_rates=[0.6, 0.7, 0.5, 0.6, 0.7],
        build_numbers=[100, 99, 97, 94, 90])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(next_run, 85)

  def testSequentialNextRunReady(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    data_points = self._GenerateDataPoints(
        pass_rates=[0.6, 0.8, 0.7, 1.0, 1.0, 1.0, 1.0, 1.0],
        build_numbers=[100, 99, 97, 94, 93, 92, 91, 90])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(next_run, 95)

  def testSequentialNextRunFirstTime(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    data_points = self._GenerateDataPoints(
        pass_rates=[0.6, 0.8, 0.7, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        build_numbers=[100, 99, 97, 95, 94, 93, 92, 91, 90])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(next_run, 96)

  def testSequentialNextRunFoundFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    data_points = self._GenerateDataPoints(
        pass_rates=[0.6, 0.8, 0.7, 0.8, 1.0, 1.0, 1.0, 1.0, 1.0],
        build_numbers=[100, 99, 97, 95, 94, 93, 92, 91, 90])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(result, 95)
    self.assertEqual(next_run, -1)

  def testSequentialNextRunDone(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    data_points = self._GenerateDataPoints(
        pass_rates=[0.6, 0.8, 0.7, 0.8, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        build_numbers=[100, 99, 97, 96, 95, 94, 93, 92, 91, 90])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(result, 96)
    self.assertEqual(next_run, -1)

  def testNextBuildWhenTestNotExistingAfterStableInARow(self):
    data_points = self._GenerateDataPoints(
        pass_rates=[0.8, 1.0, 1.0, -1], build_numbers=[100, 80, 70, 60])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(81, next_run)

  def testNextBuildWhenTestNotExistingAfterFlakeInARow(self):
    data_points = self._GenerateDataPoints(
        pass_rates=[0.8, 0.7, 0.75, -1], build_numbers=[100, 80, 70, 60])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(61, next_run)

  def testNextBuildWhenDiveHappened(self):
    data_points = self._GenerateDataPoints(
        pass_rates=[0.3, 0.8], build_numbers=[100, 80])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(79, next_run)

  def testNextBuildWhenRiseHappened(self):
    data_points = self._GenerateDataPoints(
        pass_rates=[0.3, 0.8, 0.3], build_numbers=[100, 99, 98])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(95, next_run)

  def testNextBuildWhenDivedOut(self):
    data_points = self._GenerateDataPoints(
        pass_rates=[0.3, 0.8, 0.8, 0.7, 0.8, 0.9],
        build_numbers=[100, 99, 98, 97, 96, 95])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEquals(100, result)
    self.assertEqual(-1, next_run)

  def testNextBuildWhenDivedOutSequence(self):
    data_points = self._GenerateDataPoints(
        pass_rates=[0.3, 0.2, 0.8, 0.7, 0.8, 0.9, 0.8],
        build_numbers=[100, 99, 97, 96, 05, 94, 93])

    next_run, result = _GetNextBuildNumber(
        data_points, DEFAULT_CONFIG_DATA['check_flake_settings'])
    self.assertEqual(-1, result)
    self.assertEqual(98, next_run)

  def testNextBuildNumberIsSmallerThanLastBuildNumber(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 60
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.data_points = self._GenerateDataPoints(
        pass_rates=[1.0, 1.0, 1.0, 1.0, 1.0],
        build_numbers=[100, 99, 98, 97, 96])
    analysis.status = analysis_status.RUNNING
    analysis.Save()

    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.COMPLETED)

    self.MockPipeline(recursive_flake_pipeline.UpdateFlakeBugPipeline,
                      '',
                      expected_args=[analysis.key.urlsafe()],
                      expected_kwargs={})

    pipeline = NextBuildNumberPipeline(
        master_name, builder_name, master_build_number, build_number, step_name,
        test_name, analysis.version_number)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, master_build_number, step_name, test_name)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  def testUpdateAnalysisUponCompletionError(self):
    expected_error = {
        'code': 1,
        'message': 'some error message'
    }
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    recursive_flake_pipeline._UpdateAnalysisStatusUponCompletion(
        analysis, 100, analysis_status.COMPLETED, expected_error)
    self.assertEqual(expected_error, analysis.error)
    self.assertEqual(analysis.suspected_flake_build_number, 100)

  def testGetListOfNearbyBuildNumbers(self):
    self.assertEqual(
        [1],
        recursive_flake_pipeline._GetListOfNearbyBuildNumbers(1, 0))
    self.assertEqual(
        [1],
        recursive_flake_pipeline._GetListOfNearbyBuildNumbers(1, -1))
    self.assertEqual(
        [1, 2],
        recursive_flake_pipeline._GetListOfNearbyBuildNumbers(1, 1))
    self.assertEqual(
        [1, 2, 3],
        recursive_flake_pipeline._GetListOfNearbyBuildNumbers(1, 2))
    self.assertEqual(
        [2, 1, 3],
        recursive_flake_pipeline._GetListOfNearbyBuildNumbers(2, 1))
    self.assertEqual(
        [100, 99, 101, 98, 102, 97, 103, 96, 104, 95, 105],
        recursive_flake_pipeline._GetListOfNearbyBuildNumbers(100, 5))

  def testIsSwarmingTaskSufficientNoSwarmingTasks(self):
    self.assertFalse(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            None, 100))

  def testIsSwarmingTaskSufficientForCacheHitInsufficientIterations(self):
    desired_iterations = 200
    flake_swarming_task = FlakeSwarmingTask.Create(
        'm', 'b', 12345, 's', 't')
    flake_swarming_task.tries = 100
    flake_swarming_task.status = analysis_status.COMPLETED
    self.assertFalse(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testIsSwarmingTaskSufficientForCacheHitError(self):
    desired_iterations = 100
    flake_swarming_task = FlakeSwarmingTask.Create(
        'm', 'b', 12345, 's', 't')
    flake_swarming_task.tries = 200
    flake_swarming_task.status = analysis_status.ERROR
    self.assertFalse(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testIsSwarmingTaskSufficientForCacheHitPending(self):
    desired_iterations = 100
    flake_swarming_task = FlakeSwarmingTask.Create(
        'm', 'b', 12345, 's', 't')
    flake_swarming_task.tries = desired_iterations
    flake_swarming_task.status = analysis_status.PENDING
    self.assertTrue(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testIsSwarmingTaskSufficientForCacheHitRunning(self):
    desired_iterations = 100
    flake_swarming_task = FlakeSwarmingTask.Create(
        'm', 'b', 12345, 's', 't')
    flake_swarming_task.tries = desired_iterations
    flake_swarming_task.status = analysis_status.RUNNING
    self.assertTrue(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testIsSwarmingTaskSufficientForCacheHitCompleted(self):
    desired_iterations = 100
    flake_swarming_task = FlakeSwarmingTask.Create(
        'm', 'b', 12345, 's', 't')
    flake_swarming_task.tries = desired_iterations
    flake_swarming_task.status = analysis_status.COMPLETED
    self.assertTrue(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testGetBestBuildNumberToRunWithStepSizeZero(self):
    self.assertEqual(
        12345,
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            'm', 'b', 12345, 's', 't', 0, 100))

  def testGetBestBuildNumberToRunWithNoNearbyNeighbors(self):
    self.assertEqual(
        12345,
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            'm', 'b', 12345, 's', 't', 10, 100))

  def testGetBestBuildNumberToRunWithNearbyNeighborRunnning(self):
    master_name = 'm'
    builder_name = 'b'
    preferred_run_build_number = 1000
    cached_build_number = 997
    step_name = 's'
    test_name = 't'
    number_of_iterations = 100
    step_size = 10

    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, cached_build_number, step_name, test_name,
        status=analysis_status.RUNNING, number_of_iterations=100)

    self.assertEqual(
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            master_name, builder_name, preferred_run_build_number, step_name,
            test_name, step_size, number_of_iterations),
        cached_build_number)

  def testGetBestBuildNumberToRunWithNearbyNeighborCompleted(self):
    # Completed build should take precendence over running build, even if it's
    # farther away.
    master_name = 'm'
    builder_name = 'b'
    preferred_run_build_number = 1000
    running_cached_build_number = 997
    completed_cached_build_number = 996
    step_name = 's'
    test_name = 't'
    number_of_iterations = 100
    step_size = 10

    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, running_cached_build_number, step_name,
        test_name, status=analysis_status.RUNNING, number_of_iterations=100)

    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, completed_cached_build_number, step_name,
        test_name, status=analysis_status.COMPLETED, number_of_iterations=100)

    self.assertEqual(
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            master_name, builder_name, preferred_run_build_number, step_name,
            test_name, step_size, number_of_iterations),
        completed_cached_build_number)

  def testGetBestBuildNumberToRunWithMultipleInProgress(self):
    # Completed builds should take precendence over running build, even if it's
    # farther away.
    master_name = 'm'
    builder_name = 'b'
    preferred_run_build_number = 1000
    running_cached_build_number_1 = 997
    running_cached_build_number_2 = 996
    step_name = 's'
    test_name = 't'
    number_of_iterations = 100
    step_size = 10

    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, running_cached_build_number_1, step_name,
        test_name, status=analysis_status.RUNNING, number_of_iterations=100)

    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, running_cached_build_number_2, step_name,
        test_name, status=analysis_status.RUNNING, number_of_iterations=100)

    self.assertEqual(
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            master_name, builder_name, preferred_run_build_number, step_name,
            test_name, step_size, number_of_iterations),
        running_cached_build_number_1)

  def testGetBestBuildNumberToRunPendingAndRunning(self):
    # Running builds should take precedence over pending builds.
    master_name = 'm'
    builder_name = 'b'
    preferred_run_build_number = 1000
    running_cached_build_number_1 = 997
    running_cached_build_number_2 = 996
    step_name = 's'
    test_name = 't'
    number_of_iterations = 100
    step_size = 10

    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, running_cached_build_number_1, step_name,
        test_name, status=analysis_status.PENDING, number_of_iterations=100)

    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, running_cached_build_number_2, step_name,
        test_name, status=analysis_status.RUNNING, number_of_iterations=100)

    self.assertEqual(
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            master_name, builder_name, preferred_run_build_number, step_name,
            test_name, step_size, number_of_iterations),
        running_cached_build_number_2)

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  @mock.patch.object(
      recursive_flake_pipeline, '_GetNextBuildNumber', return_value=(-1, 100))
  @mock.patch.object(
      recursive_flake_pipeline.confidence, 'SteppinessForBuild',
      return_value=0.4)
  def testNextBuildPipelineForSuspectedBuildWithLowConfidence(self, *_):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.COMPLETED
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    data_point = DataPoint()
    data_point.pass_rate = .08
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    self.MockPipeline(recursive_flake_pipeline.RecursiveFlakePipeline,
                      '',
                      expected_args=[],
                      expected_kwargs={})
    self.MockPipeline(recursive_flake_pipeline.RecursiveFlakeTryJobPipeline,
                      '',
                      expected_args=[],
                      expected_kwargs={})

    pipeline = NextBuildNumberPipeline(
        master_name, builder_name, master_build_number, build_number,
        step_name, test_name, analysis.version_number)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    self.assertTrue(analysis.completed)
    self.assertEqual(100, analysis.suspected_flake_build_number)
    self.assertEqual(0.4, analysis.confidence_in_suspected_build)

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  @mock.patch.object(
      recursive_flake_pipeline, '_GetNextBuildNumber', return_value=(-1, 100))
  @mock.patch.object(
      recursive_flake_pipeline.confidence, 'SteppinessForBuild',
      return_value=0.7)
  @mock.patch.object(
      recursive_flake_pipeline.MasterFlakeAnalysis,
      'GetDataPointOfSuspectedBuild',
      return_value=DataPoint())
  def testNextBuildPipelineForSuspectedBuildWithEmptyBlamelist(self, *_):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.COMPLETED
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    data_point = DataPoint()
    data_point.pass_rate = .08
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    self.MockPipeline(recursive_flake_pipeline.RecursiveFlakePipeline,
                      '',
                      expected_args=[],
                      expected_kwargs={})
    self.MockPipeline(recursive_flake_pipeline.RecursiveFlakeTryJobPipeline,
                      '',
                      expected_args=[],
                      expected_kwargs={})

    pipeline = NextBuildNumberPipeline(
        master_name, builder_name, master_build_number, build_number,
        step_name, test_name, analysis.version_number)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    self.assertTrue(analysis.completed)
    self.assertEqual(100, analysis.suspected_flake_build_number)
    self.assertEqual(0.7, analysis.confidence_in_suspected_build)

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  @mock.patch.object(
      recursive_flake_pipeline, '_GetNextBuildNumber', return_value=(-1, 100))
  @mock.patch.object(
      recursive_flake_pipeline.confidence, 'SteppinessForBuild',
      return_value=0.7)
  @mock.patch.object(
      recursive_flake_pipeline.confidence, 'SteppinessForCommitPosition',
      return_value=0.8)
  @mock.patch.object(
      recursive_flake_try_job_pipeline, 'CreateCulprit',
      return_value=FlakeCulprit.Create('cr', 'r1', 10, 'http://', 0.8))
  def testNextBuildPipelineForSuspectedBuildWithOnlyOneCommit(self, *_):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.COMPLETED
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    data_point = DataPoint()
    data_point.pass_rate = .08
    data_point.blame_list = ['r1']
    data_point.commit_position = 10
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    self.MockPipeline(recursive_flake_pipeline.RecursiveFlakePipeline,
                      '',
                      expected_args=[],
                      expected_kwargs={})
    self.MockPipeline(recursive_flake_pipeline.RecursiveFlakeTryJobPipeline,
                      '',
                      expected_args=[],
                      expected_kwargs={})

    pipeline = NextBuildNumberPipeline(
        master_name, builder_name, master_build_number, build_number,
        step_name, test_name, analysis.version_number)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    self.assertTrue(analysis.completed)
    self.assertEqual(100, analysis.suspected_flake_build_number)
    self.assertEqual(0.7, analysis.confidence_in_suspected_build)
    self.assertIsNotNone(analysis.culprit)
    self.assertEqual(10, analysis.culprit.commit_position)
    self.assertEqual(0.8, analysis.culprit.confidence)

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  @mock.patch.object(
      recursive_flake_pipeline, '_GetNextBuildNumber', return_value=(-1, 100))
  @mock.patch.object(
      recursive_flake_pipeline.confidence, 'SteppinessForBuild',
      return_value=0.7)
  def testNextBuildPipelineForSuspectedBuildWithMultipleCommits(self, *_):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.COMPLETED
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    data_point = DataPoint()
    data_point.pass_rate = .08
    data_point.build_number = 100
    data_point.blame_list = ['r1', 'r2', 'r3']
    data_point.commit_position = 10
    analysis.data_points.append(data_point)
    analysis.put()

    self.MockPipeline(recursive_flake_pipeline.RecursiveFlakePipeline,
                      '',
                      expected_args=[],
                      expected_kwargs={})
    self.MockPipeline(recursive_flake_pipeline.RecursiveFlakeTryJobPipeline,
                      '',
                      expected_args=[analysis.key.urlsafe(), 9, 'r2'],
                      expected_kwargs={})

    pipeline = NextBuildNumberPipeline(
        master_name, builder_name, master_build_number, build_number,
        step_name, test_name, analysis.version_number)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    self.assertTrue(analysis.completed)
    self.assertEqual(100, analysis.suspected_flake_build_number)
    self.assertEqual(0.7, analysis.confidence_in_suspected_build)
    self.assertIsNone(analysis.culprit)
