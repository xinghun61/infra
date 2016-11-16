# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall.test import wf_testcase
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)


class TriggerFlakeSwarmingTaskPipelineTest(wf_testcase.WaterfallTestCase):

  def testGetArgs(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    tests = ['t']

    self.assertEqual(
        (master_name, builder_name, build_number, step_name, tests[0]),
        TriggerFlakeSwarmingTaskPipeline()._GetArgs(
            master_name, builder_name, build_number, step_name, tests))

  def testGetSwarmingTask(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name).put()

    task = TriggerFlakeSwarmingTaskPipeline()._GetSwarmingTask(
        master_name, builder_name, build_number, step_name, test_name)

    self.assertEqual(master_name, task.master_name)
    self.assertEqual(builder_name, task.builder_name)
    self.assertEqual(build_number, task.build_number)
    self.assertEqual(step_name, task.step_name)
    self.assertEqual(test_name, task.test_name)

  def testCreateSwarmingTask(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    task = TriggerFlakeSwarmingTaskPipeline()._CreateSwarmingTask(
        master_name, builder_name, build_number, step_name, test_name)
    self.assertEqual(master_name, task.master_name)
    self.assertEqual(builder_name, task.builder_name)
    self.assertEqual(build_number, task.build_number)
    self.assertEqual(step_name, task.step_name)
    self.assertEqual(test_name, task.test_name)

  def testGetIterationsToRerun(self):
    expected_iterations = 50
    self.UpdateUnitTestConfigSettings(
        config_property='check_flake_settings',
        override_data={'iterations_to_rerun': expected_iterations})
    self.assertEqual(
        expected_iterations,
        TriggerFlakeSwarmingTaskPipeline()._GetIterationsToRerun())
