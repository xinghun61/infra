# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from libs import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.wf_swarming_task import WfSwarmingTask
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.swarming_task_request import SwarmingTaskRequest
from waterfall.test import wf_testcase
from waterfall.trigger_base_swarming_task_pipeline import (
    TriggerBaseSwarmingTaskPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)
from waterfall.trigger_swarming_task_pipeline import TriggerSwarmingTaskPipeline


class TriggerBaseSwarmingTaskPipelineTest(wf_testcase.WaterfallTestCase):

  def testNoNewSwarmingTaskIsNeeded(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    tests = ['a.b']

    swarming_task = WfSwarmingTask.Create(
        master_name, builder_name, build_number, step_name)
    swarming_task.status = analysis_status.RUNNING
    swarming_task.task_id = 'task_id'
    swarming_task.put()

    pipeline = TriggerSwarmingTaskPipeline()
    task_id = pipeline.run(
        master_name, builder_name, build_number, step_name, tests)
    self.assertEqual('task_id', task_id)

  def testWaitingForTheTaskId(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    tests = ['a.b']

    swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, tests[0])
    swarming_task.status = analysis_status.PENDING
    swarming_task.put()

    def MockedSleep(*_):
      swarming_task = FlakeSwarmingTask.Get(
          master_name, builder_name, build_number, step_name, tests[0])
      self.assertEqual(analysis_status.PENDING, swarming_task.status)
      swarming_task.status = analysis_status.RUNNING
      swarming_task.task_id = 'task_id'
      swarming_task.put()
    self.mock(time, 'sleep', MockedSleep)

    pipeline = TriggerFlakeSwarmingTaskPipeline()
    task_id = pipeline.run(
        master_name, builder_name, build_number, step_name, tests)
    self.assertEqual('task_id', task_id)

  def testTriggerANewSwarmingTask(self):
    def MockedDownloadSwarmingTaskData(*_):
      return [{'task_id': '1'}, {'task_id': '2'}]
    self.mock(swarming_util, 'ListSwarmingTasksDataByTags',
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
          'tags': ['master:a', 'buildername:b', 'name:a_tests'],
          'user': 'user',
      })
    self.mock(swarming_util, 'GetSwarmingTaskRequest',
              MockedGetSwarmingTaskRequest)

    new_request_json = {}
    def MockedTriggerSwarmingTask(new_request, *_):
      new_request_json.update(new_request.Serialize())
      return 'new_task_id', None
    self.mock(swarming_util, 'TriggerSwarmingTask', MockedTriggerSwarmingTask)

    def MockedGetSwarmingTaskName(*_):
      return 'new_task_name'
    self.mock(TriggerBaseSwarmingTaskPipeline, '_GetSwarmingTaskName',
              MockedGetSwarmingTaskName)

    master_name = 'm'
    builder_name = 'b'
    build_number = 234
    step_name = 'a_tests on platform'
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
            'extra_args': [
                '--flag=value',
                '--gtest_filter=a.b:a.c',
                '--gtest_repeat=10',
                '--test-launcher-retry-limit=0',
                '--gtest_also_run_disabled_tests',
            ],
            'grace_period_secs': 30,
            'idempotent': False,
            'inputs_ref': {'a': 1},
            'io_timeout_secs': 1200,
        },
        'tags': [
            'ref_master:%s' % master_name,
            'ref_buildername:%s' % builder_name,
            'ref_buildnumber:%s' % build_number,
            'ref_stepname:%s' % step_name,
            'ref_task_id:1',
            'ref_name:a_tests',
            'purpose:identify-flake',
        ],
        'user': '',
        'pubsub_auth_token': 'https://goo.gl/yYhr29',
        'pubsub_topic': 'projects/findit-for-me/topics/swarm',
        'pubsub_userdata': '{"Message-Type": "SwarmingTaskStatusChange"}',
    }

    pipeline = TriggerSwarmingTaskPipeline()
    new_task_id = pipeline.run(
        master_name, builder_name, build_number, step_name, tests)
    self.assertEqual('new_task_id', new_task_id)
    self.assertEqual(expected_new_request_json, new_request_json)

    swarming_task = WfSwarmingTask.Get(
        master_name, builder_name, build_number, step_name)
    self.assertIsNotNone(swarming_task)
    self.assertEqual('new_task_id', swarming_task.task_id)
    self.assertEqual(tests, swarming_task.parameters['tests'])
    self.assertEqual(
        waterfall_config.GetSwarmingSettings()['iterations_to_rerun'],
        swarming_task.parameters['iterations_to_rerun'])
