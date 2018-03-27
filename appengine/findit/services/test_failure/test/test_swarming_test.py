# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock

from google.appengine.ext import ndb

from dto.run_swarming_task_parameters import RunSwarmingTaskParameters
from infra_api_clients.swarming.swarming_task_request import SwarmingTaskRequest
from infra_api_clients.swarming import swarming_util
from libs import analysis_status
from model.wf_swarming_task import WfSwarmingTask
from services.parameters import BuildKey
from services import swarmed_test_util
from services import swarming
from services.test_failure import test_swarming
from waterfall.test import wf_testcase

_SAMPLE_REQUEST_JSON = {
    'expiration_secs':
        '3600',
    'name':
        'findit/ref_task_id/ref_task_id/2018-03-15 00:00:00 000000',
    'parent_task_id':
        '',
    'priority':
        '25',
    'properties': {
        'command':
            'cmd',
        'dimensions': [{
            'key': 'k',
            'value': 'v'
        }],
        'env': [{
            'key': 'a',
            'value': '1'
        },],
        'execution_timeout_secs':
            '10',
        'extra_args': [
            '--flag=value',
            '--gtest_filter=a.b:a.c',
            '--gtest_repeat=30',
            '--test-launcher-retry-limit=0',
            '--gtest_also_run_disabled_tests',
        ],
        'grace_period_secs':
            '30',
        'idempotent':
            False,
        'inputs_ref': {
            'isolatedserver': 'isolatedserver',
            'isolated': 'sha'
        },
        'io_timeout_secs':
            '1200',
    },
    'tags': [
        'ref_master:m',
        'ref_buildername:b',
        'ref_buildnumber:4',
        'ref_stepname:s',
        'ref_name:test',
    ],
    'user':
        '',
    'pubsub_auth_token':
        'auth_token',
    'pubsub_topic':
        'projects/app-id/topics/swarming',
    'pubsub_userdata':
        json.dumps({
            'runner_id': 'runner_id'
        }),
}


class TestSwarmingTest(wf_testcase.WaterfallTestCase):

  def testNeedANewSwarmingTaskCreateANewOne(self):
    need, urlsafe_task_key = test_swarming.NeedANewSwarmingTask(
        'm', 'b', 1, 's', False)
    self.assertTrue(need)

    swarming_task = ndb.Key(urlsafe=urlsafe_task_key).get()
    self.assertIsNotNone(swarming_task)

  def testNeedANewSwarmingTaskForce(self):
    swarming_task = WfSwarmingTask.Create('m', 'b', 2, 's')
    swarming_task.status = analysis_status.ERROR
    swarming_task.put()
    need, urlsafe_task_key = test_swarming.NeedANewSwarmingTask(
        'm', 'b', 2, 's', True)
    self.assertTrue(need)
    swarming_task = ndb.Key(urlsafe=urlsafe_task_key).get()
    self.assertEqual(analysis_status.PENDING, swarming_task.status)

  def testNotNeedANewSwarmingTask(self):
    swarming_task = WfSwarmingTask.Create('m', 'b', 3, 's')
    swarming_task.status = analysis_status.ERROR
    swarming_task.put()
    need, _ = test_swarming.NeedANewSwarmingTask('m', 'b', 3, 's', False)
    self.assertFalse(need)

  @mock.patch.object(test_swarming, 'FinditHttpClient', return_value=None)
  @mock.patch.object(
      swarming_util, 'TriggerSwarmingTask', return_value=('new_task_id', None))
  @mock.patch.object(swarming, 'CreateNewSwarmingTaskRequestTemplate')
  @mock.patch.object(
      swarming,
      'GetReferredSwarmingTaskRequestInfo',
      return_value=('task_id', 'ref_request'))
  def testTriggerSwarmingTask(self, mock_ref, mock_create, mock_trigger, _):
    runner_id = 'runner_id'
    master_name = 'm'
    builder_name = 'b'
    build_number = 6
    step_name = 's'
    tests = ['test']
    WfSwarmingTask.Create(master_name, builder_name, build_number,
                          step_name).put()
    parameters = RunSwarmingTaskParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        step_name=step_name,
        tests=tests)
    new_request = SwarmingTaskRequest.FromSerializable(_SAMPLE_REQUEST_JSON)
    mock_create.return_value = new_request
    task_id = test_swarming.TriggerSwarmingTask(parameters, runner_id)
    self.assertEqual('new_task_id', task_id)

    mock_ref.assert_called_once_with(master_name, builder_name, build_number,
                                     step_name, None)
    mock_create.assert_called_once_with(
        'runner_id',
        'task_id',
        'ref_request',
        master_name,
        builder_name,
        step_name,
        tests,
        10,
        use_new_pubsub=True)
    mock_trigger.assert_called_once_with('chromium-swarm.appspot.com',
                                         new_request, None)

  def testOnSwarmingTaskTriggered(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 6
    step_name = 's'
    task = WfSwarmingTask.Create(master_name, builder_name,
                                          build_number, step_name)
    task.put()
    task_id = 'task_id'
    tests = ['t']
    iterations = 100
    new_request = {
        'expiration_secs':
            '3600',
        'name':
            'findit/ref_task_id/ref_task_id/2018-03-15 00:00:00 000000',
        'parent_task_id':
            '',
        'priority':
            '25',
        'properties': {
            'command':
                'cmd',
            'dimensions': [{
                'key': 'k',
                'value': 'v'
            }],
            'env': [{
                'key': 'a',
                'value': '1'
            },],
            'execution_timeout_secs':
                '10',
            'extra_args': [
                '--flag=value',
                '--gtest_filter=a.b:a.c',
                '--gtest_repeat=30',
                '--test-launcher-retry-limit=0',
                '--gtest_also_run_disabled_tests',
            ],
            'grace_period_secs':
                '30',
            'idempotent':
                False,
            'inputs_ref': {
                'isolatedserver': 'isolatedserver',
                'isolated': 'sha'
            },
            'io_timeout_secs':
                '1200',
        },
        'tags': [
            'ref_master:m',
            'ref_buildername:b',
            'ref_buildnumber:4',
            'ref_stepname:s',
            'ref_name:test',
        ],
        'user':
            '',
        'pubsub_auth_token':
            'auth_token',
        'pubsub_topic':
            'projects/app-id/topics/swarming',
        'pubsub_userdata':
            json.dumps({
                'runner_id': 'runner_id'
            }),
    }
    test_swarming.OnSwarmingTaskTriggered(
      master_name, builder_name,
      build_number, step_name, tests,
      'task_id', iterations,
      SwarmingTaskRequest.FromSerializable(new_request))

    task = WfSwarmingTask.Get(master_name, builder_name,
                                          build_number, step_name)
    self.assertEqual(task.task_id, task_id)