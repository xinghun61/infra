# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants
from common.pipeline_wrapper import pipeline_handlers
from model import analysis_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake import recursive_flake_pipeline
from waterfall.flake.recursive_flake_pipeline import NextBuildNumberPipeline
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline
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

  def testRecursiveFlakePipeline(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 124
    build_number = 124
    run_build_number = 124
    step_name = 's'
    test_name = 't'
    test_result_future = 'test_result_future'
    queue_name = constants.DEFAULT_QUEUE
    task_id = 'task_id'

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
                       step_name, test_name, test_result_future,
                       queue_name],
        expected_kwargs={})

    rfp = RecursiveFlakePipeline(master_name, builder_name, build_number,
                                 step_name, test_name, master_build_number,
                                 queue_name=queue_name)
    rfp.start(queue_name=queue_name)
    self.execute_queued_tasks()

  def testNextBuildPipelineForNewRecursion(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 124
    build_number = 124
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    queue_name = constants.DEFAULT_QUEUE

    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    analysis.build_numbers.append(124)
    analysis.put()

    queue_name = {'x': False}
    # Unused argument (class method calls in python) - pylint: disable=W0613
    def my_mocked_run(arg1, queue_name):
      queue_name['x'] = True

    self.mock(
        recursive_flake_pipeline.RecursiveFlakePipeline, 'start', my_mocked_run)
    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, step_name, test_name, test_result_future,
        queue_name)
    self.assertTrue(queue_name['x'])

  def testNextBuildPipelineForNewRecursionWhenDone(self):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 124
    build_number = 124
    step_name = 's'
    test_name = 't'
    test_result_future = 'trf'
    queue_name = constants.DEFAULT_QUEUE

    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.PENDING
    )
    analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                       build_number, step_name, test_name)
    for _ in range(10):
      analysis.build_numbers.append(124)
    analysis.put()

    queue_name = {'x': False}

    # Unused argument (class method calls in python) - pylint: disable=W0613
    def my_mocked_run(*_):
      queue_name['x'] = True  # pragma: no cover

    self.mock(
        recursive_flake_pipeline.RecursiveFlakePipeline, 'start', my_mocked_run)
    NextBuildNumberPipeline.run(
        NextBuildNumberPipeline(), master_name, builder_name,
        master_build_number, step_name, test_name, test_result_future,
        queue_name)
    self.assertFalse(queue_name['x'])
