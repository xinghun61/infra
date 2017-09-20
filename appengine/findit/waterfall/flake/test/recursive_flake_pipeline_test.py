# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import copy
import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.wf_swarming_task import WfSwarmingTask

from waterfall import swarming_util
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

  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipeline(self, *_):
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

  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  def testRecursiveFlakePipelineWithForceFlag(self, *_):
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

  @mock.patch.object(flake_constants, 'BASE_COUNT_DOWN_SECONDS', 0)
  @mock.patch.object(swarming_util, 'BotsAvailableForTask')
  def testTryLaterIfNoAvailableBots(self, mock_fn, *_):
    mock_fn.side_effect = [False, True]

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

    pipeline_job = RecursiveFlakePipeline(
        analysis.key.urlsafe(),
        build_number,
        None,
        None,
        None,
        use_nearby_neighbor=False)

    pipeline_job.start(queue_name=queue_name)
    self.execute_queued_tasks()

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

  @mock.patch.object(swarming_util, 'GetETAToStartAnalysis', return_value=None)
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
