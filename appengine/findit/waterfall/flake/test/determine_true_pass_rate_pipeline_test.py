# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import copy
import mock
from common import constants

from gae_libs.pipeline_wrapper import pipeline_handlers

from libs import analysis_status
from libs import time_util
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.wf_swarming_task import WfSwarmingTask
from waterfall.flake import confidence
from waterfall import swarming_util
from waterfall.flake import flake_constants
from waterfall.flake import flake_analysis_util
from waterfall.flake import lookback_algorithm
from waterfall.flake import determine_true_pass_rate_pipeline
from waterfall.flake.analyze_flake_for_build_number_pipeline import (
    AnalyzeFlakeForBuildNumberPipeline)
from waterfall.flake.determine_true_pass_rate_pipeline import (
    DetermineTruePassRatePipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class DetermineTruePassRatePipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_HasPassRateConverged',
      side_effect=[False, True])
  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_MinimumIterationsReached',
      return_value=True)
  @mock.patch.object(
      flake_analysis_util, 'EstimateSwarmingIterationTimeout', return_value=60)
  @mock.patch.object(
      flake_analysis_util,
      'CalculateNumberOfIterationsToRunWithinTimeout',
      return_value=60)
  def testDetermineTruePassRatePipeline(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    rerun = False
    iterations = 60
    timeout = 3600

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(
            build_number=build_number, pass_rate=1.0, iterations=0)
    ]
    analysis.put()

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), build_number, iterations, timeout, rerun
        ])

    pipeline_job = DetermineTruePassRatePipeline(analysis.key.urlsafe(),
                                                 build_number, rerun)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_HasPassRateConverged',
      side_effect=[False, True])
  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_MinimumIterationsReached',
      return_value=True)
  @mock.patch.object(
      flake_analysis_util, 'EstimateSwarmingIterationTimeout', return_value=60)
  @mock.patch.object(
      flake_analysis_util,
      'CalculateNumberOfIterationsToRunWithinTimeout',
      return_value=60)
  def testDetermineTruePassRatePipelineWithRerun(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    rerun = True
    iterations = 60
    timeout = 3600

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(
            build_number=build_number, pass_rate=1.0, iterations=0)
    ]
    analysis.put()

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), build_number, iterations, timeout, rerun
        ])

    pipeline_job = DetermineTruePassRatePipeline(analysis.key.urlsafe(),
                                                 build_number, rerun)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_HasPassRateConverged',
      return_value=True)
  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_MinimumIterationsReached',
      return_value=True)
  @mock.patch.object(
      flake_analysis_util, 'EstimateSwarmingIterationTimeout', return_value=60)
  @mock.patch.object(
      flake_analysis_util,
      'CalculateNumberOfIterationsToRunWithinTimeout',
      return_value=60)
  def testDetermineTruePassRatePipelineWithoutIterationsCompleted(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    rerun = False
    iterations = 60
    timeout = 3600

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(build_number=build_number, pass_rate=1.0)
    ]
    analysis.put()

    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = analysis_status.COMPLETED
    flake_swarming_task.put()

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), build_number, iterations, timeout, rerun
        ])

    pipeline_job = DetermineTruePassRatePipeline(analysis.key.urlsafe(),
                                                 build_number, rerun)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_HasPassRateConverged',
      side_effect=[False, True])
  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_MinimumIterationsReached',
      return_value=True)
  @mock.patch.object(
      flake_analysis_util, 'EstimateSwarmingIterationTimeout', return_value=60)
  @mock.patch.object(
      flake_analysis_util,
      'CalculateNumberOfIterationsToRunWithinTimeout',
      return_value=60)
  def testDetermineTruePassRatePipelineWithRepeat(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    rerun = False
    iterations = 60
    timeout = 3600

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = analysis_status.COMPLETED
    flake_swarming_task.put()

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), build_number, iterations, timeout, rerun
        ])

    pipeline_job = DetermineTruePassRatePipeline(analysis.key.urlsafe(),
                                                 build_number, rerun)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_HasPassRateConverged',
      side_effect=[False, True])
  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_MinimumIterationsReached',
      return_value=True)
  def testDetermineTruePassRatePipelineWithLastSwarmingTaskError(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    rerun = False
    iterations = 1
    timeout = 3600

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.start_time = datetime(2017, 6, 26, 23)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.swarming_task_attempts_for_build = (
        flake_constants.MAX_SWARMING_TASK_RETRIES_PER_BUILD - 1)
    analysis.put()

    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = analysis_status.ERROR
    flake_swarming_task.error = {'code': swarming_util.TIMED_OUT}
    flake_swarming_task.put()

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), build_number, iterations, timeout, rerun
        ])

    pipeline_job = DetermineTruePassRatePipeline(
        analysis.key.urlsafe(),
        build_number,
        rerun,
        previous_pass_rate=1.0,
        previous_iterations_completed=100)

    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    # analysis.swarming_task_attempts_for_build should have been reset on
    # abort.
    self.assertEqual(0, analysis.swarming_task_attempts_for_build)

  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_HasPassRateConverged',
      side_effect=[False, True])
  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_MinimumIterationsReached',
      return_value=True)
  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_TestDoesNotExist',
      return_value=False)
  def testDetermineTruePassRatePipelineWithOneSwarmingTaskError(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    rerun = False
    iterations = flake_constants.DEFAULT_ITERATIONS_TO_RUN_AFTER_TIMEOUT
    timeout = 3600

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.swarming_task_attempts_for_build = 0
    analysis.put()

    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = analysis_status.ERROR
    flake_swarming_task.error = {'code': swarming_util.TIMED_OUT}
    flake_swarming_task.put()

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), build_number, iterations, timeout, rerun
        ])

    pipeline_job = DetermineTruePassRatePipeline(
        analysis.key.urlsafe(),
        build_number,
        rerun,
        previous_pass_rate=1.0,
        previous_iterations_completed=100)

    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_HasPassRateConverged',
      side_effect=[False, True])
  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_MinimumIterationsReached',
      return_value=True)
  @mock.patch.object(
      determine_true_pass_rate_pipeline,
      '_TestDoesNotExist',
      return_value=False)
  def testDetermineTruePassRatePipelineWithSwarmingTaskErrorOnFirstIteration(
      self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    rerun = False
    iterations = 30
    timeout = 3600

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.swarming_task_attempts_for_build = 0
    analysis.put()

    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = analysis_status.ERROR
    flake_swarming_task.error = {'code': swarming_util.TIMED_OUT}
    flake_swarming_task.put()

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), build_number, iterations, timeout, rerun
        ])

    pipeline_job = DetermineTruePassRatePipeline(analysis.key.urlsafe(),
                                                 build_number, rerun)

    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertEqual(0, analysis.swarming_task_attempts_for_build)

  @mock.patch.object(
      flake_analysis_util, 'EstimateSwarmingIterationTimeout', return_value=60)
  @mock.patch.object(
      flake_analysis_util,
      'CalculateNumberOfIterationsToRunWithinTimeout',
      return_value=60)
  def testDetermineTruePassRatePipelineWithTestDoesNotExist(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    rerun = False
    iterations = 60
    timeout = 3600

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(build_number=build_number, pass_rate=-1)
    ]
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.put()

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), build_number, iterations, timeout
        ],
        expected_kwargs={'rerun': rerun})

    pipeline_job = DetermineTruePassRatePipeline(analysis.key.urlsafe(),
                                                 build_number, rerun)

    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  def testDetermineTruePassRatePipelineMaxIterationsReached(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    rerun = False

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.data_points = [
        DataPoint.Create(build_number, 1, 'task_id', iterations=401)
    ]
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = analysis_status.COMPLETED
    flake_swarming_task.put()

    pipeline_job = DetermineTruePassRatePipeline(analysis.key.urlsafe(),
                                                 build_number, rerun)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  def testDetermineTruePassRatePipelineMaxRetriesReached(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    rerun = False

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.start_time = datetime(2017, 6, 26, 23)
    analysis.status = analysis_status.PENDING
    analysis.swarming_task_attempts_for_build = 10
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR
    task.put()

    pipeline_job = DetermineTruePassRatePipeline(analysis.key.urlsafe(),
                                                 build_number, rerun)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    self.assertEqual(analysis_status.ERROR, analysis.status)

  def testUpdateAnalysisWithSwarmingTaskError(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.start_time = datetime(2017, 6, 26, 23)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    expected_error_json = {
        'error': 'Swarming task failed',
        'message': 'The last swarming task did not complete as expected'
    }
    determine_true_pass_rate_pipeline._UpdateAnalysisWithSwarmingTaskError(
        task, analysis)
    self.assertEqual(expected_error_json, analysis.error)
    self.assertEqual(analysis_status.ERROR, analysis.status)

  def testHasPassRateConverged(self):
    self.assertFalse(
        determine_true_pass_rate_pipeline._HasPassRateConverged(None, None))
    self.assertFalse(
        determine_true_pass_rate_pipeline._HasPassRateConverged(None, 1))
    self.assertFalse(
        determine_true_pass_rate_pipeline._HasPassRateConverged(1, None))
    self.assertFalse(
        determine_true_pass_rate_pipeline._HasPassRateConverged(1, 0))
    self.assertFalse(
        determine_true_pass_rate_pipeline._HasPassRateConverged(0, 1))
    self.assertFalse(
        determine_true_pass_rate_pipeline._HasPassRateConverged(.2, .15))
    self.assertFalse(
        determine_true_pass_rate_pipeline._HasPassRateConverged(.15, .2))
    self.assertTrue(
        determine_true_pass_rate_pipeline._HasPassRateConverged(.2, .151))
    self.assertTrue(
        determine_true_pass_rate_pipeline._HasPassRateConverged(.151, .2))

  def testMinimumIterationsReached(self):
    self.assertFalse(
        determine_true_pass_rate_pipeline._MinimumIterationsReached(None, None))
    self.assertFalse(
        determine_true_pass_rate_pipeline._MinimumIterationsReached(1, None))
    self.assertFalse(
        determine_true_pass_rate_pipeline._MinimumIterationsReached(None, 1))
    self.assertFalse(
        determine_true_pass_rate_pipeline._MinimumIterationsReached(100, 99))
    self.assertFalse(
        determine_true_pass_rate_pipeline._MinimumIterationsReached(50, 51))
    self.assertFalse(
        determine_true_pass_rate_pipeline._MinimumIterationsReached(-1, 1))
    self.assertTrue(
        determine_true_pass_rate_pipeline._MinimumIterationsReached(101, 102))
    self.assertTrue(
        determine_true_pass_rate_pipeline._MinimumIterationsReached(500, 600))

  def testGetTimeoutForTask(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    self.assertEqual(3600,
                     determine_true_pass_rate_pipeline._GetTimeoutForTask(
                         analysis, 10, 10))
    self.assertEqual(3600,
                     determine_true_pass_rate_pipeline._GetTimeoutForTask(
                         analysis, 59, 60))
    self.assertEqual(3600,
                     determine_true_pass_rate_pipeline._GetTimeoutForTask(
                         analysis, -10, 10))
    self.assertEqual(3600,
                     determine_true_pass_rate_pipeline._GetTimeoutForTask(
                         analysis, 10, -10))
    self.assertEqual(10000,
                     determine_true_pass_rate_pipeline._GetTimeoutForTask(
                         analysis, 100, 100))

  def testCalculateRunParametersForSwarmingTask(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    self.assertEqual((30, 3600),
                     determine_true_pass_rate_pipeline.
                     _CalculateRunParametersForSwarmingTask(analysis, 123))

  def testCalculateRunParametersForSwarmingTaskExceedsMaxTasks(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.data_points = [
        DataPoint.Create(
            build_number=123, iterations=100, elapsed_seconds=100, pass_rate=1)
    ]
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    self.assertEqual((200, 3600),
                     determine_true_pass_rate_pipeline.
                     _CalculateRunParametersForSwarmingTask(analysis, 123))

  def testCalculateRunParametersForSwarmingTaskWithSumLessThanAnHour(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(
            build_number=build_number,
            pass_rate=1,
            iterations=10,
            elapsed_seconds=1000)
    ]
    analysis.put()

    self.assertEqual((18, 3600),
                     determine_true_pass_rate_pipeline.
                     _CalculateRunParametersForSwarmingTask(
                         analysis, build_number))

  def testCalculateRunParametersForSwarmingTaskWithSumMoreThanAnHour(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(
            build_number=build_number,
            pass_rate=1,
            iterations=1,
            elapsed_seconds=4000)
    ]
    analysis.put()

    self.assertEqual((1, 8000),
                     determine_true_pass_rate_pipeline.
                     _CalculateRunParametersForSwarmingTask(
                         analysis, build_number))

  def testTestDoesNotExist(self):
    self.assertFalse(determine_true_pass_rate_pipeline._TestDoesNotExist(1, 1))
    self.assertFalse(determine_true_pass_rate_pipeline._TestDoesNotExist(0, 1))
    self.assertFalse(
        determine_true_pass_rate_pipeline._TestDoesNotExist(None, 1))
    self.assertFalse(
        determine_true_pass_rate_pipeline._TestDoesNotExist(0, None))
    self.assertTrue(determine_true_pass_rate_pipeline._TestDoesNotExist(-1, 1))
    self.assertTrue(determine_true_pass_rate_pipeline._TestDoesNotExist(1, -1))
    self.assertTrue(
        determine_true_pass_rate_pipeline._TestDoesNotExist(None, -1))
    self.assertTrue(
        determine_true_pass_rate_pipeline._TestDoesNotExist(-1, None))

  def testCheckSwarmingTaskForError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.swarming_task_attempts_for_build = 0
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR
    task.error = {'code': swarming_util.TIMED_OUT}
    task.put()

    self.assertEqual(
        swarming_util.TIMED_OUT,
        determine_true_pass_rate_pipeline._GetSwarmingTaskErrorCode(
            analysis, task, 1.0))
    self.assertIsNone(
        determine_true_pass_rate_pipeline._GetSwarmingTaskErrorCode(
            analysis, task, None))

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    self.assertEqual(
        None,
        determine_true_pass_rate_pipeline._GetSwarmingTaskErrorCode(
            analysis, task, 1.0))
    self.assertIsNone(
        determine_true_pass_rate_pipeline._GetSwarmingTaskErrorCode(
            analysis, task, 1.0))
    self.assertIsNone(
        determine_true_pass_rate_pipeline._GetSwarmingTaskErrorCode(
            analysis, None, 1.0))
    self.assertEqual(1, analysis.swarming_task_attempts_for_build)
