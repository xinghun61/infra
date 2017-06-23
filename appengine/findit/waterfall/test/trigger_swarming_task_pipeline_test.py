# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.wf_swarming_task import WfSwarmingTask
from waterfall.test import wf_testcase
from waterfall.trigger_swarming_task_pipeline import TriggerSwarmingTaskPipeline


class TriggerSwarmingTaskPipelineTest(wf_testcase.WaterfallTestCase):

  def testGetArgs(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    tests = []

    self.assertEqual((master_name, builder_name, build_number, step_name),
                     TriggerSwarmingTaskPipeline()._GetArgs(
                         master_name, builder_name, build_number, step_name,
                         tests))

  def testGetSwarmingTask(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'

    WfSwarmingTask.Create(master_name, builder_name, build_number,
                          step_name).put()

    task = TriggerSwarmingTaskPipeline()._GetSwarmingTask(
        master_name, builder_name, build_number, step_name)

    self.assertEqual(master_name, task.master_name)
    self.assertEqual(builder_name, task.builder_name)
    self.assertEqual(build_number, task.build_number)
    self.assertEqual(step_name, task.step_name)

  def testCreateSwarmingTask(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'

    task = TriggerSwarmingTaskPipeline()._CreateSwarmingTask(
        master_name, builder_name, build_number, step_name)
    self.assertEqual(master_name, task.master_name)
    self.assertEqual(builder_name, task.builder_name)
    self.assertEqual(build_number, task.build_number)
    self.assertEqual(step_name, task.step_name)

  def testGetIterationsToRerun(self):
    expected_iterations = 50
    self.UpdateUnitTestConfigSettings(
        config_property='swarming_settings',
        override_data={'iterations_to_rerun': expected_iterations})
    self.assertEqual(expected_iterations,
                     TriggerSwarmingTaskPipeline()._GetIterationsToRerun())
