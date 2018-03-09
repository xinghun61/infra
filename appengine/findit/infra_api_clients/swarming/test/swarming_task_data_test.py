# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra_api_clients.swarming import swarming_task_data


class SwarmingTaskDataTest(unittest.TestCase):

  def testGetTagsDict(self):
    raw_tags = ['master:m', 'buildername:b']
    expected_tags = {'master': ['m'], 'buildername': ['b']}
    self.assertEqual(expected_tags, swarming_task_data._GetTagsDict(raw_tags))

  def testSwarmingTaskData(self):
    item = {
        'outputs_ref': {
            'isolate': 'isolate',
            'namespace': 'namespace',
            'isolateserver': 'isolateserver'
        },
        'tags': ['data:data', 'buildername:Win7 Tests (1)'],
        'failure': True,
        'internal_failure': False
    }
    task_data = swarming_task_data.SwarmingTaskData(item)
    self.assertTrue(task_data.non_internal_failure)
    self.assertEqual('data', task_data.inputs_ref_sha)
