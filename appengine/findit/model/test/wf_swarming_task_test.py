# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.wf_swarming_task import WfSwarmingTask


class WfSwarmingTaskTest(unittest.TestCase):
  def testClassifiedTests(self):
    task =  WfSwarmingTask.Create('m', 'b', 121, 'browser_tests')
    task.tests_statuses = {
        'TestSuite1.test1': {
            'total_run': 2,
            'SUCCESS': 2
        },
        'TestSuite1.test2': {
            'total_run': 4,
            'SUCCESS': 2,
            'FAILURE': 2
        },
        'TestSuite1.test3': {
            'total_run': 6,
            'FAILURE': 6
        }
    }

    expected_classified_tests = {
        'flaky_tests': ['TestSuite1.test2', 'TestSuite1.test1'],
        'reliable_tests': ['TestSuite1.test3']
    }

    self.assertEqual(expected_classified_tests, task.classified_tests)
