# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from libs import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall import swarming_util
from waterfall.swarming_task_request import SwarmingTaskRequest
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
        override_data={'swarming_rerun': {
                           'iterations_to_rerun': expected_iterations}})
    self.assertEqual(
        expected_iterations,
        TriggerFlakeSwarmingTaskPipeline()._GetIterationsToRerun())

  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags',
                     return_value=[{'task_id': '1'}])
  @mock.patch.object(swarming_util, 'TriggerSwarmingTask',
                     return_value=('new_task_id', None))
  @mock.patch.object(TriggerFlakeSwarmingTaskPipeline, '_GetSwarmingTaskName',
                     return_value='new_task_id')
  @mock.patch.object(swarming_util, 'GetSwarmingTaskRequest')
  def testRerunSwarmingTaskForSameBuild(self, mock_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    iterations = 200

    flake_pipeline = TriggerFlakeSwarmingTaskPipeline()
    task = flake_pipeline._CreateSwarmingTask(
        master_name, builder_name, build_number, step_name, test_name)
    task.task_id = 'task_id1'
    task.status = analysis_status.COMPLETED
    task.parameters['iterations_to_rerun'] = 100
    task.put()

    mock_fn.return_value = SwarmingTaskRequest.Deserialize({
          'expiration_secs': 3600,
          'name': 'ref_task_request',
          'parent_task_id': 'pti',
          'priority': 25,
          'properties': {
              'command': 'cmd',
              'dimensions': [{'key': 'k', 'value': 'v'}],
              'env': [
                  {'key': 'a', 'value': '1'},
                  {'key': 'GTEST_SHARD_INDEX', 'value': '1'},
                  {'key': 'GTEST_TOTAL_SHARDS', 'value': '5'},
              ],
              'execution_timeout_secs': 3600,
              'extra_args': [
                  '--flag=value',
                  '--gtest_filter=d.f',
                  '--test-launcher-filter-file=path/to/filter/file',
              ],
              'grace_period_secs': 30,
              'idempotent': True,
              'inputs_ref': {'a': 1},
              'io_timeout_secs': 1200,
          },
          'tags': ['master:m', 'buildername:b', 'name:s'],
          'user': 'user',
      })


    new_task_id = flake_pipeline.run(master_name, builder_name, build_number,
                                     step_name, [test_name], iterations)

    self.assertEqual('new_task_id', new_task_id)

    swarming_task = flake_pipeline._GetSwarmingTask(
        master_name, builder_name, build_number, step_name, test_name)
    self.assertIsNotNone(swarming_task)
    self.assertEqual('new_task_id', swarming_task.task_id)
    self.assertEqual([test_name], swarming_task.parameters['tests'])
    self.assertEqual(200, swarming_task.parameters['iterations_to_rerun'])
