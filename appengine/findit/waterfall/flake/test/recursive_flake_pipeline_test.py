# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common import constants
from common.pipeline_wrapper import pipeline_handlers
from model import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake import recursive_flake_pipeline
from waterfall.flake.recursive_flake_pipeline import get_next_run
from waterfall.flake.recursive_flake_pipeline import NextBuildNumberPipeline
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline
from waterfall.flake.recursive_flake_pipeline import sequential_next_run
from waterfall.test import wf_testcase


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
      self, master_name, builder_name, build_number,
      step_name, test_name, status):
    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = status
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
    with mock.patch('common.time_util.GetDatetimeInTimezone') as timezone_func:
      timezone_func.side_effect = [mocked_pst_now, None]
      self.assertEqual(mocked_utc_now,
                       recursive_flake_pipeline._GetETAToStartAnalysis(False))

  def testGetETAToStartAnalysisWhenTriggeredOffPeakHoursOnPSTWeekday(self):
    # Tuesday 1am in PST, and Tuesday 8am in UTC.
    mocked_pst_now = datetime(2016, 9, 20, 1, 0, 0, 0)
    mocked_utc_now = datetime(2016, 9, 20, 8, 0, 0, 0)
    self.MockUTCNow(mocked_utc_now)
    self.MockUTCNowWithTimezone(mocked_utc_now)
    with mock.patch('common.time_util.GetDatetimeInTimezone') as timezone_func:
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
    with mock.patch('common.time_util.GetDatetimeInTimezone') as (
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
    test_result_future = 'test_result_future'
    queue_name = constants.DEFAULT_QUEUE
    task_id = 'task_id'

    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0

    }

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
                       analysis.version_number, test_result_future,
                       flakiness_algorithm_results_dict],
        expected_kwargs={'manually_triggered': False})

    rfp = RecursiveFlakePipeline(
        master_name, builder_name, build_number, step_name, test_name,
        analysis.version_number, master_build_number,
        flakiness_algorithm_results_dict=flakiness_algorithm_results_dict)

    rfp.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  def testNextBuildPipelineForNewRecursionFirstFlake(self, _mocked_eta_func):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0

    }
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

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        analysis.version_number, test_result_future,
        flakiness_algorithm_results_dict)
    self.assertEquals(flakiness_algorithm_results_dict['flakes_in_a_row'], 1)

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  def testNextBuildPipelineForNewRecursionFirstStable(self, _mocked_eta_func):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0
    }
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
    data_point.pass_rate = 0
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name,
        test_name, analysis.version_number, test_result_future,
        flakiness_algorithm_results_dict)
    self.assertEquals(flakiness_algorithm_results_dict['stable_in_a_row'], 1)

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  def testNextBuildPipelineForNewRecursionFlakeInARow(self, _mocked_eta_func):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 4,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0

    }
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
    data_point.pass_rate = 0
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name,
        test_name, analysis.version_number, test_result_future,
        flakiness_algorithm_results_dict)
    self.assertEquals(flakiness_algorithm_results_dict['stabled_out'], True)

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  def testNextBuildPipelineForNewRecursionStableInARow(self, _mocked_eta_func):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 4,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0

    }
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
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name,
        test_name, analysis.version_number, test_result_future,
        flakiness_algorithm_results_dict)
    self.assertEquals(flakiness_algorithm_results_dict['flaked_out'], True)

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  def testNextBuildPipelineForNewRecursionLessThanLastBuildNumber(
      self, _mocked_eta_func):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 200,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0
    }
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
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    queue_name = {'x': False}
    def my_mocked_run(*_, **__):
      queue_name['x'] = True  # pragma: no cover

    self.mock(
        recursive_flake_pipeline.RecursiveFlakePipeline, 'start', my_mocked_run)
    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        analysis.version_number, test_result_future,
        flakiness_algorithm_results_dict)
    self.assertFalse(queue_name['x'])

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  def testNextBuildPipelineForFailedSwarmingTask(self, _mocked_eta_func):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0

    }
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.ERROR
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    queue_name = {'x': False}
    def my_mocked_run(*_, **__):
      queue_name['x'] = True  # pragma: no cover

    self.mock(
        recursive_flake_pipeline.RecursiveFlakePipeline, 'start', my_mocked_run)
    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name, 1,
        test_result_future, flakiness_algorithm_results_dict)
    self.assertFalse(queue_name['x'])

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  def testNextBuildPipelineForNewRecursionStabledFlakedOut(
      self, _mocked_eta_func):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    queue_name = constants.DEFAULT_QUEUE
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 4,
        'stable_in_a_row': 0,
        'stabled_out': True,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': 200,
        'upper_boundary': 210,
        'lower_boundary_result': 'FLAKE',
        'sequential_run_index': 0
    }
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
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    queue_name = {'x': False}
    def my_mocked_run(*_, **__):
      queue_name['x'] = True  # pragma: no cover

    self.mock(
        recursive_flake_pipeline.RecursiveFlakePipeline, 'start', my_mocked_run)
    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        analysis.version_number, test_result_future,
        flakiness_algorithm_results_dict)
    self.assertTrue(queue_name['x'])

  def testGetNextRunSetStableLowerBoundary(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.pass_rate = 1
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 4,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': True,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': 120,
        'lower_boundary_result': None,
        'sequential_run_index': 0
    }

    get_next_run(analysis, flakiness_algorithm_results_dict)
    self.assertEqual(flakiness_algorithm_results_dict['lower_boundary'],
                     build_number)
    self.assertEqual(flakiness_algorithm_results_dict['lower_boundary_result'],
                     'STABLE')

  def testGetNextRunSetFlakeLowerBoundary(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': True,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0
    }
    get_next_run(analysis, flakiness_algorithm_results_dict)
    self.assertEqual(flakiness_algorithm_results_dict['lower_boundary'],
                     build_number)
    self.assertEqual(flakiness_algorithm_results_dict['lower_boundary_result'],
                     'FLAKE')

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
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': True,
        'flaked_out': True,
        'last_build_number': 0,
        'lower_boundary': 100,
        'upper_boundary': 110,
        'lower_boundary_result': 'STABLE',
        'sequential_run_index': 0
    }
    next_run = sequential_next_run(analysis, flakiness_algorithm_results_dict)
    self.assertEqual(next_run, 101)

  def testSequentialFoundBorderFlake(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': True,
        'flaked_out': True,
        'last_build_number': 0,
        'lower_boundary': 100,
        'upper_boundary': 110,
        'lower_boundary_result': 'STABLE',
        'sequential_run_index': 1
    }
    next_run = sequential_next_run(analysis, flakiness_algorithm_results_dict)
    self.assertEqual(next_run, False)
    self.assertEqual(analysis.suspected_flake_build_number, 101)

  def testSequentialFoundBorderStable(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.pass_rate = 1
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': True,
        'flaked_out': True,
        'last_build_number': 0,
        'lower_boundary': 100,
        'upper_boundary': 110,
        'lower_boundary_result': 'FLAKE',
        'sequential_run_index': 1
    }
    next_run = sequential_next_run(analysis, flakiness_algorithm_results_dict)
    self.assertEqual(next_run, False)
    self.assertEqual(analysis.suspected_flake_build_number, 101)

  def testSequentialDidntFindBorderStable(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.pass_rate = 1
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': True,
        'flaked_out': True,
        'last_build_number': 0,
        'lower_boundary': 100,
        'upper_boundary': 110,
        'lower_boundary_result': 'STABLE',
        'sequential_run_index': 1
    }
    next_run = sequential_next_run(analysis, flakiness_algorithm_results_dict)
    self.assertEqual(next_run, 102)
    self.assertEqual(analysis.suspected_flake_build_number, None)

  @mock.patch.object(
      recursive_flake_pipeline, '_GetETAToStartAnalysis', return_value=None)
  def testNextBuildPipelineStabledOutFlakedOutFirstTime(self, _mocked_eta_func):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': True,
        'flaked_out': True,
        'last_build_number': 0,
        'lower_boundary': 100,
        'upper_boundary': 110,
        'lower_boundary_result': None,
        'sequential_run_index': 0

    }
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
    data_point.pass_rate = 1
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        analysis.version_number, test_result_future,
        flakiness_algorithm_results_dict)
    self.assertEquals(
        flakiness_algorithm_results_dict['sequential_run_index'], 1)

  def testNextBuildWhenTestNotExistingAfterStableInARow(self):
    master = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    master.data_points = self._GenerateDataPoints(
        pass_rates=[0.8, 1.0, 1.0, -1], build_numbers=[100, 80, 70, 60])

    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 2,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0,
    }

    next_run = get_next_run(master, flakiness_algorithm_results_dict)
    self.assertEqual(81, next_run)
    self.assertTrue(flakiness_algorithm_results_dict['stabled_out'])
    self.assertTrue(flakiness_algorithm_results_dict['flaked_out'])
    self.assertEqual(80, flakiness_algorithm_results_dict['lower_boundary'])
    self.assertEqual('STABLE',
                     flakiness_algorithm_results_dict['lower_boundary_result'])

  def testNextBuildWhenTestNotExistingAfterFlakeInARow(self):
    master = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    master.data_points = self._GenerateDataPoints(
        pass_rates=[0.8, 0.7, 0.75, -1], build_numbers=[100, 80, 70, 60])
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 3,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0,
    }

    next_run = get_next_run(master, flakiness_algorithm_results_dict)
    self.assertEqual(61, next_run)
    self.assertTrue(flakiness_algorithm_results_dict['stabled_out'])
    self.assertTrue(flakiness_algorithm_results_dict['flaked_out'])
    self.assertEqual(60, flakiness_algorithm_results_dict['lower_boundary'])
    self.assertEqual('STABLE',
                     flakiness_algorithm_results_dict['lower_boundary_result'])

  def testNextBuildNumberIsLargerThanStartingBuildNumber(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 60
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 3,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 0,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0
    }
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, master_build_number, step_name,
        test_name, status=analysis_status.RUNNING)
    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.COMPLETED)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.data_points = self._GenerateDataPoints(
        pass_rates=[1.0, 1.0, 1.0, -1], build_numbers=[100, 80, 70, 60])
    analysis.put()

    pipeline = NextBuildNumberPipeline()
    pipeline.run(
        master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        analysis.version_number, test_result_future,
        flakiness_algorithm_results_dict)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, master_build_number, step_name, test_name)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  def testNextBuildNumberIsSmallerThanLastBuildNumber(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 60
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 3,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': 59,
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0
    }
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.data_points = self._GenerateDataPoints(
        pass_rates=[1.0, 1.0, 1.0, 1.0], build_numbers=[100, 80, 70, 60])
    analysis.status = analysis_status.RUNNING
    analysis.Save()

    self._CreateAndSaveFlakeSwarmingTask(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.COMPLETED)

    pipeline = NextBuildNumberPipeline()
    pipeline.run(
        master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        analysis.version_number, test_result_future,
        flakiness_algorithm_results_dict)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, master_build_number, step_name, test_name)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
