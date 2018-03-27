# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock

from infra_api_clients import http_client_util
from infra_api_clients.swarming import swarming_util
from infra_api_clients.swarming.swarming_task_request import SwarmingTaskRequest
from waterfall.test import wf_testcase


class SwarmingTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testGetSwarmingTaskRequest(self, mock_get):
    task_request_json = {
        'expiration_secs': '2',
        'name': 'name',
        'parent_task_id': 'pti',
        'priority': '1',
        'properties': {
            'command': 'cmd',
            'dimensions': [{
                'key': 'd',
                'value': 'dv'
            }],
            'env': [{
                'key': 'e',
                'value': 'ev'
            }],
            'execution_timeout_secs': '4',
            'extra_args': ['--flag'],
            'grace_period_secs': '5',
            'idempotent': True,
            'inputs_ref': {
                'isolated': 'i',
                'isolatedserver': 'is',
                'namespace': 'ns',
            },
            'io_timeout_secs': '3',
        },
        'tags': ['tag'],
        'user': 'user',
        'pubsub_topic': None,
        'pubsub_auth_token': None,
        'pubsub_userdata': None,
    }
    task_id = '1'
    mock_get.return_value = (json.dumps(task_request_json), None)

    task_request = swarming_util.GetSwarmingTaskRequest('host', task_id, None)
    self.assertEqual(
        SwarmingTaskRequest.FromSerializable(task_request_json), task_request)

  @mock.patch.object(
      http_client_util,
      'SendRequestToServer',
      return_value=(None, {
          'code': 1,
          'message': 'error'
      }))
  def testGetSwarmingTaskRequestError(self, _):
    self.assertIsNone(
        swarming_util.GetSwarmingTaskRequest('host', 'task_id1', None))

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testTriggerSwarmingTask(self, mock_post):
    task_request_json = {
        'expiration_secs': '72000',
        'name': 'name',
        'parent_task_id': 'pti',
        'priority': '150',
        'properties': {
            'command': 'cmd',
            'dimensions': [{
                'key': 'd',
                'value': 'dv'
            }],
            'env': [{
                'key': 'e',
                'value': 'ev'
            }],
            'execution_timeout_secs': '4',
            'extra_args': ['--flag'],
            'grace_period_secs': '5',
            'idempotent': True,
            'inputs_ref': {
                'isolated': 'i'
            },
            'io_timeout_secs': '3',
        },
        'tags': ['tag', 'findit:1', 'project:Chromium', 'purpose:post-commit'],
        'user': 'user',
        'pubsub_topic': None,
        'pubsub_auth_token': None,
        'pubsub_userdata': None,
    }

    mock_post.return_value = json.dumps({'task_id': '1'}), None

    task_id, error = swarming_util.TriggerSwarmingTask(
        'host', SwarmingTaskRequest.FromSerializable(task_request_json), None)
    self.assertEqual('1', task_id)
    self.assertIsNone(error)

  @mock.patch.object(
      http_client_util,
      'SendRequestToServer',
      return_value=(None, {
          'code': 1,
          'message': 'error'
      }))
  def testTriggerSwarmingTaskError(self, _):
    request = SwarmingTaskRequest.FromSerializable({})
    task_id, error = swarming_util.TriggerSwarmingTask('host', request, None)
    self.assertIsNone(task_id)
    self.assertIsNotNone(error)

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testGetSwarmingTaskResultById(self, mock_get):
    task_id = '2944afa502297110'

    expected_outputs_ref = {
        'isolatedserver': 'isolated_server',
        'namespace': 'default-gzip',
        'isolated': 'shard1_isolated'
    }

    response_json = {
        'task_id': '1',
        'state': 'COMPLETED',
        'outputs_ref': expected_outputs_ref
    }
    mock_get.return_value = json.dumps(response_json), None

    data, error = swarming_util.GetSwarmingTaskResultById('host', task_id, None)

    self.assertEqual('COMPLETED', data['state'])
    self.assertEqual(expected_outputs_ref, data['outputs_ref'])
    self.assertIsNone(error)

  @mock.patch.object(
      http_client_util,
      'SendRequestToServer',
      return_value=(None, {
          'code': 1,
          'message': 'error'
      }))
  def testGetSwarmingTaskResultByIdError(self, _):
    data, error = swarming_util.GetSwarmingTaskResultById(
        'host', 'task_id', None)
    self.assertEqual({}, data)
    self.assertIsNotNone(error)

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testGetBotCounts(self, mock_fn):
    dimensions = {'os': 'OS', 'cpu': 'cpu'}
    content_data = {'count': '10', 'dead': '1', 'quarantined': '0', 'busy': '5'}
    mock_fn.return_value = (json.dumps(content_data), None)
    expected_counts = {
        'count': 10,
        'dead': 1,
        'quarantined': 0,
        'busy': 5,
        'available': 4
    }

    self.assertEqual(expected_counts,
                     swarming_util.GetBotCounts('host', dimensions,
                                                None).Serialize())

    expected_url = ('https://host/api/swarming/v1/bots/count?dimensions=os%3AOS'
                    '&dimensions=cpu%3Acpu')
    mock_fn.assert_called_once_with(expected_url, None)

  @mock.patch.object(
      http_client_util,
      'SendRequestToServer',
      return_value=(None, {
          'code': 1,
          'message': 'error'
      }))
  def testGetBotCountsError(self, _):
    dimensions = {'os': 'OS', 'cpu': 'cpu'}
    self.assertIsNone(swarming_util.GetBotCounts('host', dimensions, None))

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testListTasks(self, mock_fn):
    tags = {'master': 'm', 'buildername': 'b'}
    content1 = {
        'items': [{
            'failure': True,
            'internal_failure': False
        }, {
            'failure': True,
            'internal_failure': False
        }],
        'cursor':
            'cursor'
    }
    content2 = {
        'items': [{
            'failure': True,
            'internal_failure': False
        }, {
            'failure': True,
            'internal_failure': False
        }],
    }
    mock_fn.side_effect = [(json.dumps(content1), None), (json.dumps(content2),
                                                          None)]
    tasks_data = swarming_util.ListTasks('host', tags, None)
    self.assertTrue(tasks_data[0].non_internal_failure)

  @mock.patch.object(
      http_client_util, 'SendRequestToServer', return_value=(None, None))
  def testListTasksNoNewData(self, mock_fn):
    tags = {'master': 'm', 'buildername': 'b'}
    self.assertEqual([], swarming_util.ListTasks('host', tags, None))
    expected_url = ('https://host/api/swarming/v1/tasks/list?tags=master%3Am&'
                    'tags=buildername%3Ab')
    mock_fn.assert_called_once_with(expected_url, None)

  @mock.patch.object(
      http_client_util, 'SendRequestToServer', return_value=('{"a":"b"}', None))
  def testListTasksNoItem(self, _):
    tags = {'master': 'm', 'buildername': 'b'}
    self.assertEqual([], swarming_util.ListTasks('host', tags, None))

  def testParametersToQueryStringList(self):
    dimensions = ['os:OS', 'cpu:cpu']
    self.assertEqual('?dimensions=os:OS&dimensions=cpu:cpu',
                     swarming_util.ParametersToQueryString(
                         dimensions, 'dimensions'))

  def testGetTagValue(self):
    tags = ['a:1', 'b:2']
    self.assertEqual('1', swarming_util.GetTagValue(tags, 'a'))

  def testGetTagValueInvalidTag(self):
    tags = ['a:1', 'b:2']
    self.assertIsNone(swarming_util.GetTagValue(tags, 'c'))

  def testGenerateIsolatedDataOutputsref(self):
    outputs_ref = {
        'isolated': 'isolated',
        'namespace': 'namespace',
        'isolatedserver': 'isolatedserver'
    }
    self.assertEqual({
        'digest': 'isolated',
        'namespace': 'namespace',
        'isolatedserver': 'isolatedserver'
    }, swarming_util.GenerateIsolatedData(outputs_ref))

  def testGenerateIsolatedDataOutputsrefNone(self):
    self.assertEqual({}, swarming_util.GenerateIsolatedData(None))
