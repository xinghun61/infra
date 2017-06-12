# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from waterfall.swarming_task_request import SwarmingTaskRequest


class SwarmingTaskRequestTest(unittest.TestCase):

  def testSerializeAndDeserialize(self):
    data = {
        'expiration_secs': 50,
        'name': 'a swarming task',
        'parent_task_id': 'jsalf',
        'priority': 150,
        'tags': ['a'],
        'user': 'someone',
        'pubsub_topic': 'topic',
        'pubsub_auth_token': 'token',
        'pubsub_userdata': 'data',
        'properties': {
            'command': 'path/to/binary',
            'dimensions': [
                {
                    'key': 'cpu',
                    'value': 'x86-64',
                },
            ],
            'env': [
                {
                    'key': 'name',
                    'value': '1',
                },
            ],
            'execution_timeout_secs': 10,
            'grace_period_secs': 5,
            'extra_args': ['--arg=value'],
            'idempotent': True,
            'inputs_ref': {
                'namespace': 'default-gzip',
                'isolated': 'a-hash',
            },
            'io_timeout_secs': 10,
        },
    }

    task = SwarmingTaskRequest.Deserialize(data)
    self.assertEqual(data, task.Serialize())

  def testDefaultValue(self):
    task = SwarmingTaskRequest()
    self.assertEqual(3600, task.expiration_secs)
    self.assertEqual(150, task.priority)
    self.assertEqual(3600, task.execution_timeout_secs)
    self.assertEqual(30, task.grace_period_secs)
    self.assertTrue(task.idempotent)
    self.assertEqual(1200, task.io_timeout_secs)
