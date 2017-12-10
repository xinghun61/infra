# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import copy
import mock

from common import constants
from gae_libs.pipelines import pipeline_handlers
from libs import analysis_status
from libs import time_util
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.wf_swarming_task import WfSwarmingTask
from pipelines.delay_pipeline import DelayPipeline
from waterfall import build_util
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.flake import flake_constants
from waterfall.flake import recursive_flake_pipeline
from waterfall.flake.determine_true_pass_rate_pipeline import (
    DetermineTruePassRatePipeline)
from waterfall.flake.finish_build_analysis_pipeline import (
    FinishBuildAnalysisPipeline)
from waterfall.flake.next_build_number_pipeline import NextBuildNumberPipeline
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline
from waterfall.flake.save_last_attempted_swarming_task_id_pipeline import (
    SaveLastAttemptedSwarmingTaskIdPipeline)
from waterfall.flake.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA

_DEFAULT_CACHE_NAME = swarming_util.GetCacheName('pm', 'pb')


class MOCK_INFO(object):
  parent_buildername = 'pb'
  parent_mastername = 'pm'


class RecursiveFlakePipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      build_util, 'FindValidBuildNumberForStepNearby', return_value=100)
  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  @mock.patch.object(recursive_flake_pipeline, '_ShouldContinueAnalysis')
  def testRecursiveFlakePipeline(self, continue_fn, *_):
    continue_fn.side_effect = [True, False]

    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    self.MockPipeline(
        DetermineTruePassRatePipeline,
        None,
        expected_args=[analysis.key.urlsafe(), build_number, False])

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        None,
        expected_args=[analysis.key.urlsafe(), None, None, None, False])

    self.MockPipeline(
        NextBuildNumberPipeline,
        None,
        expected_args=[analysis.key.urlsafe(), 100, None, None, None])

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        use_nearby_neighbor=False,
        previous_build_number=50)
    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      swarming_util,
      'GetETAToStartAnalysis',
      return_value=datetime(2017, 12, 10, 0, 0, 0, 0))
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 12, 10, 0, 0, 0, 0))
  def testGetDelaySeconds(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertEqual(0,
                     recursive_flake_pipeline._GetDelaySeconds(
                         analysis, 0, False))
    self.assertEqual(120,
                     recursive_flake_pipeline._GetDelaySeconds(
                         analysis, 1, False))
    self.assertEqual(0,
                     recursive_flake_pipeline._GetDelaySeconds(
                         analysis, flake_constants.MAX_RETRY_TIMES + 1, False))

  @mock.patch.object(
      build_util, 'FindValidBuildNumberForStepNearby', return_value=90)
  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipelineWithUserInput(self, *_):
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

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, run_build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR
    task.put()

    self.MockPipeline(
        DetermineTruePassRatePipeline,
        None,
        expected_args=[analysis.key.urlsafe(), run_build_number, False])

    self.MockPipeline(
        NextBuildNumberPipeline,
        None,
        expected_args=[
            analysis.key.urlsafe(), run_build_number, lower_bound_build_number,
            upper_bound_build_number, iterations_to_rerun
        ])

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        None,
        expected_args=[
            analysis.key.urlsafe(), lower_bound_build_number,
            upper_bound_build_number, iterations_to_rerun, False
        ])

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        run_build_number,
        lower_bound_build_number,
        upper_bound_build_number,
        iterations_to_rerun,
        use_nearby_neighbor=False)
    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      waterfall_config,
      'GetCheckFlakeSettings',
      return_value={'throttle_flake_analyses': True})
  @mock.patch.object(flake_constants, 'BASE_COUNT_DOWN_SECONDS', 0)
  @mock.patch.object(swarming_util, 'BotsAvailableForTask')
  def testRecursiveFlakePipelineWithUpperLowerBoundsThrottled(self, *_):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    run_build_number = 100
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, run_build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR
    task.put()

    self.MockPipeline(
        DetermineTruePassRatePipeline,
        None,
        expected_args=[analysis.key.urlsafe(), build_number, False])

    self.MockPipeline(
        NextBuildNumberPipeline,
        None,
        expected_args=[analysis.key.urlsafe(), build_number, None, None, None])

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        None,
        expected_args=[analysis.key.urlsafe(), None, None, None, False])

    self.MockPipeline(DelayPipeline, None, expected_args=[0])

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        use_nearby_neighbor=False)

    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      waterfall_config,
      'GetCheckFlakeSettings',
      return_value={'throttle_flake_analyses': True})
  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(1, 1, 1))
  @mock.patch.object(
      swarming_util, 'GetETAToStartAnalysis', return_value=datetime(1, 1, 1))
  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=False)
  @mock.patch.object(FlakeSwarmingTask, 'Get')
  def testRetriesExceedMaxThrottled(self, mock_flake_swarming_task, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR
    task.put()
    mock_flake_swarming_task.return_value = task

    self.MockPipeline(
        DetermineTruePassRatePipeline,
        None,
        expected_args=[analysis.key.urlsafe(), build_number, False])

    self.MockPipeline(
        NextBuildNumberPipeline,
        None,
        expected_args=[analysis.key.urlsafe(), build_number, None, None, None])

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        None,
        expected_args=[analysis.key.urlsafe(), None, None, None, False])

    self.MockAsynchronousPipeline(DelayPipeline, 0, 0)

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        step_metadata=None,
        manually_triggered=False,
        use_nearby_neighbor=False,
        retries=5)

    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      build_util, 'FindValidBuildNumberForStepNearby', return_value=51)
  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipelineWithUpperLowerBounds(self, *_):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    lower_bound_build_number = 50
    upper_bound_build_number = 90
    run_build_number = 51
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, run_build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR
    task.put()

    self.MockPipeline(
        DetermineTruePassRatePipeline,
        None,
        expected_args=[analysis.key.urlsafe(), run_build_number, False])

    self.MockPipeline(
        NextBuildNumberPipeline,
        None,
        expected_args=[
            analysis.key.urlsafe(), run_build_number, lower_bound_build_number,
            upper_bound_build_number, None
        ])

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        None,
        expected_args=[
            analysis.key.urlsafe(), lower_bound_build_number,
            upper_bound_build_number, None, False
        ])

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        run_build_number,
        lower_bound_build_number,
        upper_bound_build_number,
        None,
        use_nearby_neighbor=False)
    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      build_util, 'FindValidBuildNumberForStepNearby', return_value=51)
  @mock.patch.object(flake_constants, 'BASE_COUNT_DOWN_SECONDS', 0)
  @mock.patch.object(swarming_util, 'BotsAvailableForTask')
  def testTryLaterIfNoAvailableBots(self, mock_fn, *_):
    mock_fn.side_effect = [False, True]

    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    lower_bound_build_number = None
    upper_bound_build_number = None
    run_build_number = 51
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, run_build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR
    task.put()

    self.MockPipeline(
        DetermineTruePassRatePipeline,
        None,
        expected_args=[analysis.key.urlsafe(), run_build_number, True])

    self.MockPipeline(
        NextBuildNumberPipeline,
        None,
        expected_args=[
            analysis.key.urlsafe(), run_build_number, lower_bound_build_number,
            upper_bound_build_number, None
        ])

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        None,
        expected_args=[
            analysis.key.urlsafe(), lower_bound_build_number,
            upper_bound_build_number, None, True
        ])

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
      build_util, 'FindValidBuildNumberForStepNearby', return_value=None)
  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipelineIfNoValidBuildsNearby(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        use_nearby_neighbor=False)
    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()
    self.assertEqual(analysis.status, analysis_status.ERROR)
    self.assertEqual('Failed to find a valid build number around 100.',
                     analysis.error['message'])

  @mock.patch.object(RecursiveFlakePipeline, 'was_aborted', return_value=True)
  def testRecursiveFlakePipelineAborted(self, *_):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.put()

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
  def testRecursiveFlakePipelineAbortedNotUpdateCompletedAnalysis(self, *_):
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

  def testRecursiveFlakePipelineFinishes(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    lower_bound = 1
    upper_bound = 10
    iterations = 100

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), lower_bound, upper_bound, iterations, False
        ])

    pipeline = RecursiveFlakePipeline(analysis.key.urlsafe(), None, lower_bound,
                                      upper_bound, iterations)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  def testRecursiveFlakePipelineFinishesIfBuildNumberIsNone(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    lower_bound = 1
    upper_bound = 10
    iterations = 100

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), lower_bound, upper_bound, iterations, False
        ])

    pipeline = RecursiveFlakePipeline(analysis.key.urlsafe(), None, lower_bound,
                                      upper_bound, iterations)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      build_util, 'FindValidBuildNumberForStepNearby', return_value=100)
  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(1, 1, 1))
  @mock.patch.object(
      swarming_util, 'GetETAToStartAnalysis', return_value=datetime(1, 1, 1))
  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=False)
  @mock.patch.object(FlakeSwarmingTask, 'Get')
  def testRetriesExceedMax(self, mock_flake_swarming_task, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR
    task.put()
    mock_flake_swarming_task.return_value = task

    self.MockPipeline(
        DetermineTruePassRatePipeline,
        None,
        expected_args=[analysis.key.urlsafe(), build_number, False])

    self.MockPipeline(
        NextBuildNumberPipeline,
        None,
        expected_args=[analysis.key.urlsafe(), build_number, None, None, None])

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        None,
        expected_args=[analysis.key.urlsafe(), None, None, None, False])

    self.MockAsynchronousPipeline(DelayPipeline, 0, 0)

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        step_metadata=None,
        manually_triggered=False,
        use_nearby_neighbor=False,
        retries=5)

    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(
      build_util, 'FindValidBuildNumberForStepNearby', return_value=100)
  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipelineWithStringBuildNumber(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = '100'
    step_name = 's'
    test_name = 't'
    queue_name = constants.DEFAULT_QUEUE

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    self.MockPipeline(
        DetermineTruePassRatePipeline,
        None,
        expected_args=[analysis.key.urlsafe(),
                       int(build_number), False])

    self.MockPipeline(
        NextBuildNumberPipeline,
        None,
        expected_args=[
            analysis.key.urlsafe(),
            int(build_number), None, None, None
        ])

    self.MockPipeline(
        FinishBuildAnalysisPipeline,
        None,
        expected_args=[analysis.key.urlsafe(), None, None, None, False])

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        use_nearby_neighbor=False)
    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  def testCanStartAnalysis(self, _):
    self.assertTrue(recursive_flake_pipeline._CanStartAnalysis(None, 0, False))
    self.assertTrue(recursive_flake_pipeline._CanStartAnalysis(None, 10, False))
    self.assertTrue(recursive_flake_pipeline._CanStartAnalysis(None, 0, True))

  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=False)
  def testCanStartAnalysisNoBotsAvailable(self, _):
    self.assertFalse(recursive_flake_pipeline._CanStartAnalysis(None, 0, False))
    self.assertTrue(recursive_flake_pipeline._CanStartAnalysis(None, 10, False))
    self.assertTrue(recursive_flake_pipeline._CanStartAnalysis(None, 0, True))

  def testShouldContinueAnalysis(self):
    self.assertTrue(recursive_flake_pipeline._ShouldContinueAnalysis(100))
    self.assertFalse(recursive_flake_pipeline._ShouldContinueAnalysis(None))
