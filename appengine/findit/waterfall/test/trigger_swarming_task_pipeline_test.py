# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from waterfall import swarming_util
from waterfall.swarming_task_request import SwarmingTaskRequest
from waterfall import trigger_swarming_task_pipeline
from waterfall.trigger_swarming_task_pipeline import TriggerSwarmingTaskPipeline


class TriggerSwarmingTaskPipelineTest(testing.AppengineTestCase):

  def testTriggerSwarmingTask(self):
    def MockedDownloadSwarmingTaskData(*_):
      return [{'task_id': '1'}, {'task_id': '2'}]
    self.mock(swarming_util, 'DownloadSwarmingTasksData',
              MockedDownloadSwarmingTaskData)

    def MockedGetSwarmingTaskRequest(ref_task_id, *_):
      self.assertEqual('1', ref_task_id)
      return SwarmingTaskRequest.Deserialize({
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
              'extra_args': ['--flag=value', '--gtest_filter=d.f'],
              'grace_period_secs': 30,
              'idempotent': True,
              'inputs_ref': {'a': 1},
              'io_timeout_secs': 1200,
          },
          'tags': ['master:a', 'buildername:b'],
          'user': 'user',
      })
    self.mock(swarming_util, 'GetSwarmingTaskRequest',
              MockedGetSwarmingTaskRequest)

    new_request_json = {}
    def MockedTriggerSwarmingTask(new_request, *_):
      new_request_json.update(new_request.Serialize())
      return 'new_task_id'
    self.mock(swarming_util, 'TriggerSwarmingTask', MockedTriggerSwarmingTask)

    def MockedGetSwarmingTaskName(*_):
      return 'new_task_name'
    self.mock(trigger_swarming_task_pipeline, '_GetSwarmingTaskName',
              MockedGetSwarmingTaskName)

    master_name = 'm'
    builder_name = 'b'
    build_number = 234
    step_name = 's'
    tests = ['a.b', 'a.c']

    expected_new_request_json = {
        'expiration_secs': 3600,
        'name': 'new_task_name',
        'parent_task_id': '',
        'priority': 25,
        'properties': {
            'command': 'cmd',
            'dimensions': [{'key': 'k', 'value': 'v'}],
            'env': [
                {'key': 'a', 'value': '1'},
            ],
            'execution_timeout_secs': 3600,
            'extra_args': ['--flag=value', '--gtest_filter=a.b:a.c'],
            'grace_period_secs': 30,
            'idempotent': False,
            'inputs_ref': {'a': 1},
            'io_timeout_secs': 1200,
        },
        'tags': ['purpose:deflake', 'ref_master:%s' % master_name,
                 'ref_buildername:%s' % builder_name,
                 'ref_buildnumber:%s' % build_number,
                 'ref_stepname:%s' % step_name,
                 'ref_task_id:1'],
        'user': '',
    }

    pipeline = TriggerSwarmingTaskPipeline()
    new_task_id = pipeline.run(
        master_name, builder_name, build_number, step_name, tests)
    self.assertEqual('new_task_id', new_task_id)
    self.assertEqual(expected_new_request_json, new_request_json)
