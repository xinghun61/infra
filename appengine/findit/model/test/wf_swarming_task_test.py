# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.test_results.classified_test_results import ClassifiedTestResults
from model.wf_swarming_task import _ClassifiedTestResult
from model.wf_swarming_task import WfSwarmingTask


class WfSwarmingTaskTest(unittest.TestCase):

  def testClassifiedTestsLegacy(self):
    task = WfSwarmingTask.Create('m', 'b', 121, 'browser_tests')
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
        },
        'TestSuite1.test4': {
            'total_run': 6,
            'SKIPPED': 6
        },
        'TestSuite1.test5': {
            'total_run': 6,
            'UNKNOWN': 6
        }
    }

    expected_classified_tests = {
        'flaky_tests': ['TestSuite1.test2', 'TestSuite1.test1'],
        'reliable_tests': ['TestSuite1.test3', 'TestSuite1.test4'],
        'unknown_tests': ['TestSuite1.test5']
    }

    self.assertEqual(expected_classified_tests, task.classified_tests)
    self.assertEqual(expected_classified_tests['reliable_tests'],
                     task.reliable_tests)
    self.assertEqual(expected_classified_tests['flaky_tests'], task.flaky_tests)

  def testStepName(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    expected_step_name = 's'
    task = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                 expected_step_name)
    self.assertEqual(expected_step_name, task.step_name)

  def testClassifiedTests(self):
    task = WfSwarmingTask.Create('m', 'b', 122, 'browser_tests')
    classified_results_dict = {
        'Unittest1.Subtest1': {
            'total_run': 1,
            'num_expected_results': 0,
            'num_unexpected_results': 1,
            'results': {
                'passes': {},
                'failures': {},
                'skips': {},
                'unknowns': {
                    'UNKNOWN': 1
                }
            }
        },
        'Unittest1.Subtest2': {
            'total_run': 3,
            'num_expected_results': 1,
            'num_unexpected_results': 2,
            'results': {
                'passes': {
                    'SUCCESS': 1
                },
                'failures': {
                    'FAILURE': 2
                },
                'skips': {},
                'unknowns': {}
            }
        },
        'Unittest2.Subtest1': {
            'total_run': 3,
            'num_expected_results': 0,
            'num_unexpected_results': 3,
            'results': {
                'passes': {},
                'failures': {
                    'FAILURE': 2
                },
                'skips': {
                    'SKIPPED': 1
                },
                'unknowns': {}
            }
        }
    }
    task.classified_test_results = task.GetClassifiedTestResults(
        ClassifiedTestResults.FromDict(classified_results_dict))

    expected_classified_tests = {
        'flaky_tests': ['Unittest1.Subtest2'],
        'reliable_tests': ['Unittest2.Subtest1'],
        'unknown_tests': ['Unittest1.Subtest1']
    }

    self.assertEqual(expected_classified_tests, task.classified_tests)
    self.assertEqual(expected_classified_tests['reliable_tests'],
                     task.reliable_tests)
    self.assertEqual(expected_classified_tests['flaky_tests'], task.flaky_tests)
