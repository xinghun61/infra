# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status

from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis

from waterfall import swarming_util
from waterfall.flake import confidence
from waterfall.flake import lookback_algorithm
from waterfall.flake import next_build_number_pipeline
from waterfall.flake.next_build_number_pipeline import NextBuildNumberPipeline
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class NextBuildNumberPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  def testNextBuildPipelineForNewRecursionFirstFlake(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    pass_rate = .08

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.data_points = [DataPoint.Create(build_number, pass_rate)]
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    pipeline = NextBuildNumberPipeline(analysis.key.urlsafe(), build_number,
                                       None, None, None)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      next_build_number_pipeline, '_IsFinished', return_value=True)
  def testNextBuildNumberPipelineReturnsNoneWhenFinished(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 59
    lower_bound_build_number = 60
    step_name = 's'
    test_name = 't'
    pass_rate = 1.0

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.RUNNING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.algorithm_parameters['swarming_rerun'][
        'max_iterations_to_rerun'] = 100
    analysis.data_points = [DataPoint.Create(build_number, pass_rate)]
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    pipeline = NextBuildNumberPipeline()
    pipeline.start_test()
    next_build_number = pipeline.run(analysis.key.urlsafe(), build_number,
                                     lower_bound_build_number, None, None)
    self.assertEqual(None, next_build_number)

  @mock.patch.object(
      lookback_algorithm, 'GetNextRunPointNumber', return_value=(1, 1, 1))
  def testNextBuildNumberPipelineWithLowerBound(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 59
    lower_bound_build_number = 60
    step_name = 's'
    test_name = 't'
    pass_rate = 1.0

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.RUNNING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.algorithm_parameters['swarming_rerun'][
        'max_iterations_to_rerun'] = 100
    analysis.data_points = [DataPoint.Create(build_number, pass_rate)]
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    with mock.patch.object(
        analysis,
        'GetDataPointsWithinBuildNumberRange') as mocked_range_function:
      pipeline = NextBuildNumberPipeline()
      pipeline.start_test()
      next_build_number = pipeline.run(analysis.key.urlsafe(), build_number,
                                       lower_bound_build_number, None, None)
      self.assertEqual(1, next_build_number)
      mocked_range_function.assertCalledWith(lower_bound_build_number, None)

  @mock.patch.object(
      lookback_algorithm, 'GetNextRunPointNumber', return_value=(1, 1, 1))
  def testNextBuildNumberWithUpperBound(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 111
    upper_bound_build_number = 110
    step_name = 's'
    test_name = 't'
    pass_rate = 1.0

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.RUNNING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.algorithm_parameters['swarming_rerun'][
        'max_iterations_to_rerun'] = 100
    analysis.data_points = [DataPoint.Create(build_number, pass_rate)]
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    with mock.patch.object(
        analysis,
        'GetDataPointsWithinBuildNumberRange') as mocked_range_function:
      pipeline = NextBuildNumberPipeline()
      pipeline.start_test()
      next_build_number = pipeline.run(analysis.key.urlsafe(), build_number,
                                       None, upper_bound_build_number, None)
      self.assertEqual(1, next_build_number)
      mocked_range_function.assertCalledWith(None, upper_bound_build_number)

  @mock.patch.object(
      lookback_algorithm,
      'GetNextRunPointNumber',
      return_value=(100, None, 200))
  @mock.patch.object(confidence, 'SteppinessForBuild', return_value=0.4)
  def testNextBuildPipelineForSuspectedBuildRerunStableBuild(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.RUNNING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.algorithm_parameters['swarming_rerun'][
        'max_iterations_to_rerun'] = 100
    analysis.data_points = [
        DataPoint.Create(101, 0.8),
        DataPoint.Create(100, 1.0)
    ]
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    pipeline = NextBuildNumberPipeline(analysis.key.urlsafe(), build_number,
                                       None, None, None)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertEqual(
        200,
        analysis.algorithm_parameters['swarming_rerun']['iterations_to_rerun'])
    self.assertEqual(analysis_status.RUNNING, analysis.status)

  def testNextBuildNumberPipelineWithFailedSwarmingTask(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.ERROR
    task.put()

    self.MockPipeline(
        UpdateFlakeBugPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline = NextBuildNumberPipeline(analysis.key.urlsafe(), build_number,
                                       None, None, None)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    expected_message = 'The last swarming task did not complete as expected'
    message_key = 'message'
    self.assertTrue(message_key in analysis.error)
    self.assertEqual(analysis.error[message_key], expected_message)

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
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']

    expected_error_json = {
        'error': 'Swarming task failed',
        'message': 'The last swarming task did not complete as expected'
    }
    next_build_number_pipeline._UpdateAnalysisWithSwarmingTaskError(
        task, analysis)
    self.assertEqual(expected_error_json, analysis.error)
    self.assertEqual(analysis_status.ERROR, analysis.status)

  def testGetEarliestBuildNumber(self):
    algorithm_settings = {'max_build_numbers_to_look_back': 10}

    self.assertEqual(5,
                     next_build_number_pipeline._GetEarliestBuildNumber(
                         5, 6, algorithm_settings))
    self.assertEqual(0,
                     next_build_number_pipeline._GetEarliestBuildNumber(
                         None, 5, algorithm_settings))
    self.assertEqual(15,
                     next_build_number_pipeline._GetEarliestBuildNumber(
                         None, 25, algorithm_settings))

  def testIsFinished(self):
    self.assertTrue(next_build_number_pipeline._IsFinished(1, 2, 3, 0))
    self.assertFalse(next_build_number_pipeline._IsFinished(1, 2, 3, 10))
    self.assertTrue(next_build_number_pipeline._IsFinished(4, 2, 3, 0))
    self.assertFalse(next_build_number_pipeline._IsFinished(4, 2, 3, 10))
    self.assertTrue(next_build_number_pipeline._IsFinished(1, 2, 3, 0))
