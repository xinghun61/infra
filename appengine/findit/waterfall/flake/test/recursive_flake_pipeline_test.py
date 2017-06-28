# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from datetime import datetime
import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from libs import time_util
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.wf_swarming_task import WfSwarmingTask
from waterfall import swarming_util
from waterfall.flake import lookback_algorithm
from waterfall.flake import recursive_flake_pipeline
from waterfall.flake.initialize_flake_try_job_pipeline import (
    InitializeFlakeTryJobPipeline)
from waterfall.flake.recursive_flake_pipeline import _NormalizeDataPoints
from waterfall.flake.recursive_flake_pipeline import NextBuildNumberPipeline
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline
from waterfall.flake.recursive_flake_try_job_pipeline import (
    RecursiveFlakeTryJobPipeline)
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA

_DEFAULT_CACHE_NAME = swarming_util.GetCacheName('pm', 'pb')


class MOCK_INFO(object):
  parent_buildername = 'pb'
  parent_mastername = 'pm'


def _GenerateDataPoint(pass_rate=None,
                       build_number=None,
                       task_id=None,
                       try_job_url=None,
                       commit_position=None,
                       git_hash=None,
                       previous_build_commit_position=None,
                       previous_build_git_hash=None,
                       blame_list=None,
                       has_valid_artifact=True):
  data_point = DataPoint()
  data_point.pass_rate = pass_rate
  data_point.build_number = build_number
  data_point.task_id = task_id
  data_point.try_job_url = try_job_url
  data_point.commit_position = commit_position
  data_point.git_hash = git_hash
  data_point.previous_build_commit_position = previous_build_commit_position
  data_point.previous_build_git_hash = previous_build_git_hash
  data_point.blame_list = blame_list if blame_list else []
  data_point.has_valid_artifact = has_valid_artifact
  return data_point


class RecursiveFlakePipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _CreateAndSaveMasterFlakeAnalysis(self, master_name, builder_name,
                                        build_number, step_name, test_name,
                                        status):
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = status
    analysis.Save()

  def _CreateAndSaveFlakeSwarmingTask(self,
                                      master_name,
                                      builder_name,
                                      build_number,
                                      step_name,
                                      test_name,
                                      status=analysis_status.PENDING,
                                      number_of_iterations=0,
                                      error=None):
    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = status
    flake_swarming_task.tries = number_of_iterations
    flake_swarming_task.error = error
    flake_swarming_task.put()

  @mock.patch.object(
      RecursiveFlakePipeline, '_BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipeline(self, _):
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
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_pipeline.TriggerFlakeSwarmingTaskPipeline,
        'task_id',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, [test_name],
            100, 3 * 60 * 60
        ],
        expected_kwargs={'force': False})

    self.MockPipeline(
        recursive_flake_pipeline.ProcessFlakeSwarmingTaskResultPipeline,
        'test_result_future',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, task_id,
            master_build_number, test_name, analysis.version_number
        ],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.NextBuildNumberPipeline,
        '',
        expected_args=[analysis.key.urlsafe(), build_number, None, None, None],
        expected_kwargs={
            'step_metadata': None,
            'use_nearby_neighbor': False,
            'manually_triggered': False
        })

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        use_nearby_neighbor=False,
        step_size=0)
    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      RecursiveFlakePipeline, '_BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipelineWithUserInput(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    run_build_number = 90
    lower_bound_build_number = 50
    upper_bound_build_number = 90
    iterations_to_rerun = 150
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE
    task_id = 'task_id'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_pipeline.TriggerFlakeSwarmingTaskPipeline,
        'task_id',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, [test_name],
            iterations_to_rerun, 3 * 60 * 60
        ],
        expected_kwargs={'force': False})

    self.MockPipeline(
        recursive_flake_pipeline.ProcessFlakeSwarmingTaskResultPipeline,
        'test_result_future',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, task_id,
            master_build_number, test_name, analysis.version_number
        ],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.NextBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), run_build_number, lower_bound_build_number,
            upper_bound_build_number, iterations_to_rerun
        ],
        expected_kwargs={
            'step_metadata': None,
            'use_nearby_neighbor': False,
            'manually_triggered': False
        })

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        run_build_number,
        lower_bound_build_number,
        upper_bound_build_number,
        iterations_to_rerun,
        use_nearby_neighbor=False,
        step_size=0)
    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      RecursiveFlakePipeline, '_BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipelineWithUpperLowerBounds(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    lower_bound_build_number = 50
    upper_bound_build_number = 90
    run_build_number = 51
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE
    task_id = 'task_id'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_pipeline.TriggerFlakeSwarmingTaskPipeline,
        'task_id',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, [test_name],
            master_build_number, 3 * 60 * 60
        ],
        expected_kwargs={'force': False})

    self.MockPipeline(
        recursive_flake_pipeline.ProcessFlakeSwarmingTaskResultPipeline,
        'test_result_future',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, task_id,
            master_build_number, test_name, analysis.version_number
        ],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.NextBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), run_build_number, lower_bound_build_number,
            upper_bound_build_number, None
        ],
        expected_kwargs={
            'step_metadata': None,
            'use_nearby_neighbor': False,
            'manually_triggered': False
        })

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        run_build_number,
        50,
        90,
        None,
        use_nearby_neighbor=False,
        step_size=0)
    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      RecursiveFlakePipeline, '_BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipelineWithForceFlag(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    lower_bound_build_number = None
    upper_bound_build_number = None
    run_build_number = 51
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE
    task_id = 'task_id'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_pipeline.TriggerFlakeSwarmingTaskPipeline,
        'task_id',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, [test_name],
            master_build_number, 3 * 60 * 60
        ],
        expected_kwargs={'force': True})

    self.MockPipeline(
        recursive_flake_pipeline.ProcessFlakeSwarmingTaskResultPipeline,
        'test_result_future',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, task_id,
            master_build_number, test_name, analysis.version_number
        ],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.NextBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), run_build_number, lower_bound_build_number,
            upper_bound_build_number, None
        ],
        expected_kwargs={
            'step_metadata': None,
            'use_nearby_neighbor': False,
            'manually_triggered': False
        })

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        run_build_number,
        lower_bound_build_number,
        upper_bound_build_number,
        None,
        force=True)
    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      RecursiveFlakePipeline, '_BotsAvailableForTask', return_value=True)
  def testNextBuildPipelineForNewRecursionFirstFlake(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.PENDING)
    self._CreateAndSaveFlakeSwarmingTask(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.COMPLETED)
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    data_point = DataPoint()
    data_point.pass_rate = .08
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    self.MockPipeline(
        recursive_flake_pipeline.RecursiveFlakePipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), 99, None, None, None, None, False, False, 1,
            0, False
        ],
        expected_kwargs={})
    pipeline = NextBuildNumberPipeline(analysis.key.urlsafe(), build_number,
                                       None, None, None)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch('waterfall.flake.recursive_flake_pipeline.RecursiveFlakePipeline')
  def testNextBuildPipelineForFailedSwarmingTask(self, mocked_pipeline):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    swarming_task_error = {
        'code': 1,
        'message': 'some failure message',
    }
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.PENDING)
    self._CreateAndSaveFlakeSwarmingTask(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.ERROR,
        error=swarming_task_error)
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    self.MockPipeline(
        recursive_flake_pipeline.UpdateFlakeBugPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline = NextBuildNumberPipeline(analysis.key.urlsafe(), build_number,
                                       None, None, None)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    mocked_pipeline.assert_not_called()
    self.assertEqual(swarming_task_error, analysis.error)

  def testNextBuildNumberWithLowerBound(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 59
    lower_bound_build_number = 60
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.data_points = [_GenerateDataPoint(pass_rate=1.0, build_number=100)]
    analysis.status = analysis_status.RUNNING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.algorithm_parameters['swarming_rerun'][
        'max_iterations_to_rerun'] = 100
    analysis.Save()

    self._CreateAndSaveFlakeSwarmingTask(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.COMPLETED)

    self.MockPipeline(
        recursive_flake_pipeline.UpdateFlakeBugPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline = NextBuildNumberPipeline(analysis.key.urlsafe(), build_number,
                                       lower_bound_build_number, None, None)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, master_build_number, step_name, test_name)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  def testNextBuildNumberWithUpperBound(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 111
    upper_bound_build_number = 110
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.data_points = [_GenerateDataPoint(pass_rate=1.0, build_number=100)]
    analysis.status = analysis_status.RUNNING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.algorithm_parameters['swarming_rerun'][
        'max_iterations_to_rerun'] = 100
    analysis.Save()

    self._CreateAndSaveFlakeSwarmingTask(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.COMPLETED)

    self.MockPipeline(
        recursive_flake_pipeline.UpdateFlakeBugPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline = NextBuildNumberPipeline(analysis.key.urlsafe(), build_number,
                                       None, upper_bound_build_number, None)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, master_build_number, step_name, test_name)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  def testUpdateAnalysisResults(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_swarming_task_id = '12345'
    recursive_flake_pipeline._UpdateAnalysisResults(
        analysis, 100, analysis_status.COMPLETED, None)
    self.assertEqual(analysis.suspected_flake_build_number, 100)
    self.assertIsNone(analysis.last_attempted_swarming_task_id)

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2017, 6, 27))
  def testUpdateAnalysisResultsWithError(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_swarming_task_id = '12345'
    recursive_flake_pipeline._UpdateAnalysisResults(
        analysis, None, analysis_status.ERROR, {'error': 'error'})
    self.assertEqual(analysis_status.ERROR, analysis.status)
    self.assertEqual(datetime(2017, 6, 27), analysis.end_time)

  def testUserSpecifiedRange(self):
    self.assertTrue(recursive_flake_pipeline._UserSpecifiedRange(123, 125))
    self.assertFalse(recursive_flake_pipeline._UserSpecifiedRange(None, 123))
    self.assertFalse(recursive_flake_pipeline._UserSpecifiedRange(123, None))
    self.assertFalse(recursive_flake_pipeline._UserSpecifiedRange(None, None))

  @mock.patch.object(
      recursive_flake_pipeline.confidence,
      'SteppinessForBuild',
      return_value=0.6)
  def testGetBuildConfidenceScore(self, _):
    self.assertIsNone(
        recursive_flake_pipeline._GetBuildConfidenceScore(None, []))
    self.assertEqual(0.6,
                     recursive_flake_pipeline._GetBuildConfidenceScore(
                         123, [DataPoint(), DataPoint()]))

  def testGetListOfNearbyBuildNumbers(self):
    self.assertEqual([1],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         1, None, None, 0))
    self.assertEqual([1],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         1, None, None, -1))
    self.assertEqual([1, 0, 2],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         1, None, None, 1))
    self.assertEqual([1, 0, 2, 3],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         1, None, None, 2))
    self.assertEqual([2, 1, 3],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         2, None, None, 1))
    self.assertEqual([100, 99, 101, 98, 102, 97, 103, 96, 104, 95, 105],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         100, None, None, 5))
    self.assertEqual([6, 5, 7, 8, 9],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         6, 5, None, 3))
    self.assertEqual([7, 6, 8, 5, 9, 10],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         7, 5, None, 3))
    self.assertEqual([8, 7, 9, 6, 5],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         8, None, 9, 3))
    self.assertEqual([8, 9],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         8, 8, 9, 3))
    self.assertEqual([9, 8],
                     recursive_flake_pipeline._GetListOfNearbyBuildNumbers(
                         9, 8, 9, 3))

  def testGetEarliestBuildNumber(self):
    algorithm_settings = {'max_build_numbers_to_look_back': 10}

    self.assertEqual(5,
                     recursive_flake_pipeline._GetEarliestBuildNumber(
                         5, 6, algorithm_settings))
    self.assertEqual(0,
                     recursive_flake_pipeline._GetEarliestBuildNumber(
                         None, 5, algorithm_settings))
    self.assertEqual(15,
                     recursive_flake_pipeline._GetEarliestBuildNumber(
                         None, 25, algorithm_settings))

  def testIsSwarmingTaskSufficientNoSwarmingTasks(self):
    self.assertFalse(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            None, 100))

  def testIsSwarmingTaskSufficientForCacheHitInsufficientIterations(self):
    desired_iterations = 200
    flake_swarming_task = FlakeSwarmingTask.Create('m', 'b', 12345, 's', 't')
    flake_swarming_task.tries = 100
    flake_swarming_task.status = analysis_status.COMPLETED
    self.assertFalse(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testIsSwarmingTaskSufficientForCacheHitError(self):
    desired_iterations = 100
    flake_swarming_task = FlakeSwarmingTask.Create('m', 'b', 12345, 's', 't')
    flake_swarming_task.tries = 200
    flake_swarming_task.status = analysis_status.ERROR
    self.assertFalse(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testIsSwarmingTaskSufficientForCacheHitPending(self):
    desired_iterations = 100
    flake_swarming_task = FlakeSwarmingTask.Create('m', 'b', 12345, 's', 't')
    flake_swarming_task.tries = desired_iterations
    flake_swarming_task.status = analysis_status.PENDING
    self.assertTrue(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testIsSwarmingTaskSufficientForCacheHitRunning(self):
    desired_iterations = 100
    flake_swarming_task = FlakeSwarmingTask.Create('m', 'b', 12345, 's', 't')
    flake_swarming_task.tries = desired_iterations
    flake_swarming_task.status = analysis_status.RUNNING
    self.assertTrue(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testIsSwarmingTaskSufficientForCacheHitCompleted(self):
    desired_iterations = 100
    flake_swarming_task = FlakeSwarmingTask.Create('m', 'b', 12345, 's', 't')
    flake_swarming_task.tries = desired_iterations
    flake_swarming_task.status = analysis_status.COMPLETED
    self.assertTrue(
        recursive_flake_pipeline._IsSwarmingTaskSufficientForCacheHit(
            flake_swarming_task, desired_iterations))

  def testGetBestBuildNumberToRunWithStepSizeZero(self):
    self.assertEqual(12345,
                     recursive_flake_pipeline._GetBestBuildNumberToRun(
                         'm', 'b', 12345, 's', 't', None, None, 0, 100))

  def testGetBestBuildNumberToRunWithNoNearbyNeighbors(self):
    self.assertEqual(12345,
                     recursive_flake_pipeline._GetBestBuildNumberToRun(
                         'm', 'b', 12345, 's', 't', None, None, 10, 100))

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
        master_name,
        builder_name,
        cached_build_number,
        step_name,
        test_name,
        status=analysis_status.RUNNING,
        number_of_iterations=100)

    self.assertEqual(
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            master_name, builder_name, preferred_run_build_number, step_name,
            test_name, None, None, step_size, number_of_iterations),
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
        master_name,
        builder_name,
        running_cached_build_number,
        step_name,
        test_name,
        status=analysis_status.RUNNING,
        number_of_iterations=100)

    self._CreateAndSaveFlakeSwarmingTask(
        master_name,
        builder_name,
        completed_cached_build_number,
        step_name,
        test_name,
        status=analysis_status.COMPLETED,
        number_of_iterations=100)

    self.assertEqual(
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            master_name, builder_name, preferred_run_build_number, step_name,
            test_name, None, None, step_size, number_of_iterations),
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
        master_name,
        builder_name,
        running_cached_build_number_1,
        step_name,
        test_name,
        status=analysis_status.RUNNING,
        number_of_iterations=100)

    self._CreateAndSaveFlakeSwarmingTask(
        master_name,
        builder_name,
        running_cached_build_number_2,
        step_name,
        test_name,
        status=analysis_status.RUNNING,
        number_of_iterations=100)

    self.assertEqual(
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            master_name, builder_name, preferred_run_build_number, step_name,
            test_name, None, None, step_size, number_of_iterations),
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
        master_name,
        builder_name,
        running_cached_build_number_1,
        step_name,
        test_name,
        status=analysis_status.PENDING,
        number_of_iterations=100)

    self._CreateAndSaveFlakeSwarmingTask(
        master_name,
        builder_name,
        running_cached_build_number_2,
        step_name,
        test_name,
        status=analysis_status.RUNNING,
        number_of_iterations=100)

    self.assertEqual(
        recursive_flake_pipeline._GetBestBuildNumberToRun(
            master_name, builder_name, preferred_run_build_number, step_name,
            test_name, None, None, step_size, number_of_iterations),
        running_cached_build_number_2)

  def testNormalizeDataPoints(self):
    data_points = [
        _GenerateDataPoint(pass_rate=0.9, build_number=2),
        _GenerateDataPoint(pass_rate=0.8, build_number=1),
        _GenerateDataPoint(pass_rate=1.0, build_number=3)
    ]
    normalized_data_points = _NormalizeDataPoints(data_points)
    self.assertEqual(normalized_data_points[0].run_point_number, 3)
    self.assertEqual(normalized_data_points[1].run_point_number, 2)
    self.assertEqual(normalized_data_points[2].run_point_number, 1)
    self.assertEqual(normalized_data_points[0].pass_rate, 1.0)
    self.assertEqual(normalized_data_points[1].pass_rate, 0.9)
    self.assertEqual(normalized_data_points[2].pass_rate, 0.8)

  @mock.patch.object(
      lookback_algorithm,
      'GetNextRunPointNumber',
      return_value=(100, None, 200))
  @mock.patch.object(
      recursive_flake_pipeline.confidence,
      'SteppinessForBuild',
      return_value=0.4)
  def testNextBuildPipelineForSuspectedBuildRerunStableBuild(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.RUNNING)
    self._CreateAndSaveFlakeSwarmingTask(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.COMPLETED)
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    data_point1 = DataPoint()
    data_point1.pass_rate = 0.8
    data_point1.build_number = 101
    analysis.data_points.append(data_point1)
    data_point2 = DataPoint()
    data_point2.pass_rate = 1.0
    data_point2.build_number = 100
    analysis.data_points.append(data_point2)
    analysis.put()

    self.MockPipeline(
        RecursiveFlakePipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), build_number, None, None, None, None, False,
            False, 0, 0, False
        ],
        expected_kwargs={})
    self.MockPipeline(
        RecursiveFlakeTryJobPipeline, '', expected_args=[], expected_kwargs={})

    pipeline = NextBuildNumberPipeline(analysis.key.urlsafe(), build_number,
                                       None, None, None)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    self.assertEqual(
        200,
        analysis.algorithm_parameters['swarming_rerun']['iterations_to_rerun'])

    self.assertEqual(analysis_status.RUNNING, analysis.status)

  @mock.patch.object(recursive_flake_pipeline, '_BASE_COUNT_DOWN_SECONDS', 0)
  @mock.patch.object(RecursiveFlakePipeline, '_BotsAvailableForTask')
  def testTryLaterIfNoAvailableBots(self, mock_fn):
    mock_fn.side_effect = [False, True]

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
        expected_args=[
            master_name, builder_name, run_build_number, step_name, [test_name]
        ],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.ProcessFlakeSwarmingTaskResultPipeline,
        'test_result_future',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, task_id,
            master_build_number, test_name, analysis.version_number
        ],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.NextBuildNumberPipeline,
        '',
        expected_args=[analysis.key.urlsafe(), build_number, None, None, None],
        expected_kwargs={
            'step_metadata': None,
            'use_nearby_neighbor': False,
            'manually_triggered': False
        })

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        use_nearby_neighbor=False,
        step_size=0)

    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  def testCheckBotsAvailabilityNone(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.Save()

    self.assertFalse(
        RecursiveFlakePipeline(analysis.key.urlsafe(), 100, None, None, None)
        ._BotsAvailableForTask(None))

  @mock.patch.object(swarming_util, 'GetSwarmingBotCounts')
  def testCheckBotsAvailability(self, mock_fn):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.Save()

    step_metadata = {'dimensions': {'os': 'OS'}}

    mock_fn.return_value = {
        'count': 20,
        'dead': 1,
        'quarantined': 0,
        'busy': 5,
        'available': 14
    }

    self.assertTrue(
        RecursiveFlakePipeline(analysis.key.urlsafe(), 100, None, None, None)
        ._BotsAvailableForTask(step_metadata))

  @mock.patch.object(swarming_util, 'GetETAToStartAnalysis', return_value=None)
  @mock.patch.object(
      RecursiveFlakePipeline, '_BotsAvailableForTask', return_value=False)
  def testRetriesExceedMax(self, *_):
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
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_pipeline.TriggerFlakeSwarmingTaskPipeline,
        'task_id',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, [test_name],
            100, 3 * 60 * 60
        ],
        expected_kwargs={'force': False})

    self.MockPipeline(
        recursive_flake_pipeline.ProcessFlakeSwarmingTaskResultPipeline,
        'test_result_future',
        expected_args=[
            master_name, builder_name, run_build_number, step_name, task_id,
            master_build_number, test_name, analysis.version_number
        ],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.NextBuildNumberPipeline,
        '',
        expected_args=[analysis.key.urlsafe(), build_number, None, None, None],
        expected_kwargs={
            'step_metadata': None,
            'use_nearby_neighbor': False,
            'manually_triggered': False
        })

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        step_metadata=None,
        manually_triggered=False,
        use_nearby_neighbor=False,
        step_size=0,
        retries=5)

    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  def testUpdateIterationsToRerunNoIterationsToUpdate(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    recursive_flake_pipeline._UpdateIterationsToRerun(analysis, None)
    self.assertEqual(analysis.algorithm_parameters,
                     DEFAULT_CONFIG_DATA['check_flake_settings'])

  def testGetIterationsToRerun(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.algorithm_parameters = {
        'swarming_rerun': {
            'iterations_to_rerun': 1
        }
    }
    self.assertEqual(1,
                     recursive_flake_pipeline._GetIterationsToRerun(
                         None, analysis))
    self.assertEqual(2,
                     recursive_flake_pipeline._GetIterationsToRerun(
                         2, analysis))

  @mock.patch.object(RecursiveFlakePipeline, 'was_aborted', return_value=True)
  def testRecursiveFlakePipelineAborted(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.Save()

    pipeline_job = RecursiveFlakePipeline(analysis.key.urlsafe(), build_number,
                                          None, None, None)
    pipeline_job._LogUnexpectedAbort()

    expected_error = {
        'error': 'RecursiveFlakePipeline was aborted unexpectedly',
        'message': 'RecursiveFlakePipeline was aborted unexpectedly'
    }

    self.assertEqual(analysis_status.ERROR, analysis.status)
    self.assertEqual(expected_error, analysis.error)

  @mock.patch.object(RecursiveFlakePipeline, 'was_aborted', return_value=True)
  def testRecursiveFlakePipelineAbortedNotUpdateCompletedAnalysis(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.Save()

    pipeline_job = RecursiveFlakePipeline(analysis.key.urlsafe(), build_number,
                                          None, None, None)
    pipeline_job._LogUnexpectedAbort()

    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  @mock.patch.object(recursive_flake_pipeline, '_IsFinished', return_value=True)
  def testRecursiveFlakePipelineInitializeFlakeTryJobPipeline(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.9, build_number=build_number),
        DataPoint.Create(pass_rate=1.0, build_number=build_number - 1)
    ]
    analysis.suspected_flake_build_number = build_number
    analysis.confidence_in_suspected_build = 0.7
    analysis.Save()

    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.put()

    self.MockPipeline(
        InitializeFlakeTryJobPipeline,
        '',
        expected_args=[analysis.key.urlsafe(), None, False],
        expected_kwargs={})
    self.MockPipeline(
        recursive_flake_pipeline.UpdateFlakeBugPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline_job = NextBuildNumberPipeline(analysis.key.urlsafe(), build_number,
                                           None, None, None, None, False, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      recursive_flake_pipeline,
      '_CanEstimateExecutionTimeFromReferenceSwarmingTask',
      return_value=False)
  def testGetHardTimeoutSecondsDefault(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'

    self.UpdateUnitTestConfigSettings(
        config_property='check_flake_settings',
        override_data={'swarming_rerun': {
            'per_iteration_timeout_seconds': 60
        }})
    self.assertEqual(3 * 60 * 60,
                     recursive_flake_pipeline._GetHardTimeoutSeconds(
                         master_name, builder_name, build_number, step_name,
                         100))

  def testGetHardTimeoutSeconds(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    reference_swarming_task = WfSwarmingTask.Create(master_name, builder_name,
                                                    build_number, step_name)
    reference_swarming_task.completed_time = datetime(2017, 4, 16, 0, 0, 40)
    reference_swarming_task.started_time = datetime(2017, 4, 16, 0, 0, 0)
    reference_swarming_task.tests_statuses = {'1': 1, '2': 1}
    reference_swarming_task.parameters = {'iterations_to_rerun': 2}
    reference_swarming_task.put()
    self.UpdateUnitTestConfigSettings(
        config_property='check_flake_settings',
        override_data={'swarming_rerun': {
            'per_iteration_timeout_seconds': 1
        }})
    self.assertEqual(60 * 60,
                     recursive_flake_pipeline._GetHardTimeoutSeconds(
                         master_name, builder_name, build_number, step_name,
                         10))
