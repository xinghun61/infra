# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
from StringIO import StringIO
import unittest

import mock

from util_scripts.experiments import trigger_tasks


class TriggerTasksTest(unittest.TestCase):

  def testParseSwarmingCommandResult(self):
    self.assertEqual(
        'abcdef000000',
        trigger_tasks.ParseSwarmingCommandResult('\n'.join([
            'ignore',
            '\t  swarming.py collect http://swarming.url abcdef000000  ',
            'ignore'
        ])))
    with self.assertRaises(trigger_tasks.NoSwarmingTaskIdException):
      trigger_tasks.ParseSwarmingCommandResult('\nsome error occurred\n\n')

  def testComposeSwarmingTaskTriggerCommand(self):
    os.environ['SWARMING_PY'] = 'not_real.py'
    expected = [
        'python', 'not_real.py', 'trigger', '-I', 'isolateserver.appspot.com',
        '-S', 'chromium-swarm.appspot.com', '-d', 'os', 'Mac', '-d', 'pool',
        'findit', '-s', '600dbeefbadd0beef0', '--', '--gtest_count=1'
    ]
    self.assertEqual(
        expected,
        trigger_tasks.ComposeSwarmingTaskTriggerCommand(
            'os:Mac,pool:findit', '600dbeefbadd0beef0', 1, '--gtest_count=%d'))

  @mock.patch('__builtin__.open')
  def testMainBadExperiment(self, mock_open):
    mock_open.return_value = StringIO(json.dumps({}))
    with self.assertRaises(AssertionError):
      trigger_tasks.main('some_path.json')
