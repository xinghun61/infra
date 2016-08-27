# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants
from common.pipeline_wrapper import pipeline_handlers
from model import analysis_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall.flake import recursive_flake_pipeline
from waterfall.flake.recursive_flake_pipeline import get_next_run
from waterfall.flake.recursive_flake_pipeline import NextBuildNumberPipeline
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline
from waterfall.flake.recursive_flake_pipeline import sequential_next_run
from waterfall.test import wf_testcase


class RecursiveFlakePipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _CreateAndSaveMasterFlakeAnalysis(
      self, master_name, builder_name, build_number,
      step_name, test_name, status):
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = status
    analysis.put()

  def _CreateAndSaveFlakeSwarmingTask(
      self, master_name, builder_name, build_number,
      step_name, test_name, status):
    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.status = status
    flake_swarming_task.put()

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

    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, master_build_number, step_name,
        test_name, status=analysis_status.PENDING
    )

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
                       master_build_number, test_name],
        expected_kwargs={})

    self.MockPipeline(
        recursive_flake_pipeline.NextBuildNumberPipeline,
        '',
        expected_args=[master_name, builder_name, master_build_number,
                       build_number, step_name, test_name,
                       test_result_future, queue_name,
                       flakiness_algorithm_results_dict],
        expected_kwargs={})

    rfp = RecursiveFlakePipeline(master_name, builder_name, build_number,
                                 step_name, test_name, master_build_number,
                                 flakiness_algorithm_results_dict=
                                 flakiness_algorithm_results_dict,
                                 queue_name=queue_name)

    rfp.start(queue_name=queue_name)
    self.execute_queued_tasks()

  def testNextBuildPipelineForNewRecursionFirstFlake(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    queue_name = constants.DEFAULT_QUEUE
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(.08)
    analysis.build_numbers.append(100)
    analysis.put()

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        test_result_future, queue_name, flakiness_algorithm_results_dict)
    self.assertEquals(flakiness_algorithm_results_dict['flakes_in_a_row'], 1)

  def testNextBuildPipelineForNewRecursionFirstStable(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    queue_name = constants.DEFAULT_QUEUE
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(0)
    analysis.build_numbers.append(100)
    analysis.put()

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name,
        test_name, test_result_future, queue_name,
        flakiness_algorithm_results_dict)
    self.assertEquals(flakiness_algorithm_results_dict['stable_in_a_row'], 1)

  def testNextBuildPipelineForNewRecursionFlakeInARow(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    queue_name = constants.DEFAULT_QUEUE
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(0)
    analysis.build_numbers.append(100)
    analysis.put()

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name,
        test_name, test_result_future, queue_name,
        flakiness_algorithm_results_dict)
    self.assertEquals(flakiness_algorithm_results_dict['stabled_out'], True)

  def testNextBuildPipelineForNewRecursionStableInARow(self):
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(.50)
    analysis.build_numbers.append(100)
    analysis.put()

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name,
        test_name, test_result_future, queue_name,
        flakiness_algorithm_results_dict)
    self.assertEquals(flakiness_algorithm_results_dict['flaked_out'], True)


  def testNextBuildPipelineForNewRecursionLessThanLastBuildNumber(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    queue_name = constants.DEFAULT_QUEUE
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(.50)
    analysis.build_numbers.append(100)
    analysis.put()

    queue_name = {'x': False}
    def my_mocked_run(arg1, queue_name):  # pylint: disable=unused-argument
      queue_name['x'] = True  # pragma: no cover

    self.mock(
        recursive_flake_pipeline.RecursiveFlakePipeline, 'start', my_mocked_run)
    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        test_result_future, queue_name, flakiness_algorithm_results_dict)
    self.assertFalse(queue_name['x'])

  def testNextBuildPipelineForFailedSwarmingTask(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    queue_name = constants.DEFAULT_QUEUE
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(.50)
    analysis.build_numbers.append(100)
    analysis.put()

    queue_name = {'x': False}
    def my_mocked_run(arg1, queue_name):  # pylint: disable=unused-argument
      queue_name['x'] = True  # pragma: no cover

    self.mock(
        recursive_flake_pipeline.RecursiveFlakePipeline, 'start', my_mocked_run)
    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        test_result_future, queue_name, flakiness_algorithm_results_dict)
    self.assertFalse(queue_name['x'])

  def testNextBuildPipelineForNewRecursionStabledFlakedOut(self):
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(.50)
    analysis.build_numbers.append(100)
    analysis.put()

    queue_name = {'x': False}
    def my_mocked_run(arg1, queue_name):  # pylint: disable=unused-argument
      queue_name['x'] = True  # pragma: no cover

    self.mock(
        recursive_flake_pipeline.RecursiveFlakePipeline, 'start', my_mocked_run)
    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        test_result_future, queue_name, flakiness_algorithm_results_dict)
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(1)
    analysis.build_numbers.append(100)
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(.5)
    analysis.build_numbers.append(100)
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(.5)
    analysis.build_numbers.append(100)
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(.5)
    analysis.build_numbers.append(100)
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(1)
    analysis.build_numbers.append(100)
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(1)
    analysis.build_numbers.append(100)
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

  def testNextBuildPipelineStabledOutFlakedOutFirstTime(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    build_number = 100
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    queue_name = constants.DEFAULT_QUEUE
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
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.success_rates.append(1)
    analysis.build_numbers.append(50)
    analysis.put()

    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, build_number, step_name, test_name,
        test_result_future, queue_name, flakiness_algorithm_results_dict)
    self.assertEquals(
        flakiness_algorithm_results_dict['sequential_run_index'], 1)
