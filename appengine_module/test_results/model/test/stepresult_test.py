#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import copy
import json
import unittest

from appengine_module.testing_utils import testing
from appengine_module.test_results.model.stepresult import StepResult
from appengine_module.test_results.model.testfile import TestFile


class StepResultTest(testing.AppengineTestCase):

  test_json_1 = {
      'builder_name': 'test_builder_name',
      'build_number': '42',
      'blink_revision': '54321',
      'chromium_revision': 'deadbeef' * 5,
      'version': '9',
      'seconds_since_epoch': '1411715603',
      'tests': {
          'test_name_1': {
              'expected': 'PASS',
              'actual': 'FAIL FAIL NOTRUN',
              'time': '4.56'
          },
          'test_name_2': {
              'expected': 'SKIP',
              'actual': 'SKIP',
              'time': '0.0004',
          },
          'test_name_3': {
              'expected': 'TEXT',
              'actual': 'REBASELINE',
              'time': '99'
          },
      },
      'num_failures_by_type': {
          'FAIL': 2,
          'NOTRUN': 1,
          'SKIP': 1,
          'REBASELINE': 1
      },
  }

  @staticmethod
  def _massage_json(j):
    for t in j['tests'].values():
      if 'time' in t:  # pragma: no branch
        t['time'] = '%.5f' % float(t['time'])
    for key in StepResult.RESULT2STR:
      j['num_failures_by_type'].setdefault(key, 0)
    return j

  def testJsonRoundTrip(self):
    self.maxDiff = None
    step_result = StepResult.fromJson(
        'test_master', 'test_step', self.test_json_1)

    self.assertEqual(step_result.master, 'test_master')
    self.assertEqual(step_result.builder_name, 'test_builder_name')
    self.assertEqual(step_result.build_number, 42)
    self.assertEqual(step_result.test_type, 'test_step')
    self.assertEqual(step_result.blink_revision, '54321')
    self.assertEqual(step_result.chromium_revision, 'deadbeef' * 5)
    self.assertEqual(step_result.version, 9)
    self.assertEqual(
        calendar.timegm(step_result.time.utctimetuple()), 1411715603)

    (master_out, test_type_out, json_out) = step_result.toJson()

    self.assertEqual(master_out, 'test_master')
    self.assertEqual(test_type_out, 'test_step')
    self.assertEqual(self._massage_json(copy.deepcopy(self.test_json_1)),
                     self._massage_json(copy.deepcopy(json_out)))

  def testFromTestFile(self):
    test_file = TestFile(master='test_master',
                         builder='test_builder_name',
                         test_type='test_step',
                         build_number=42,
                         name='test_file_name')
    test_file.save_file(test_file, json.dumps(self.test_json_1))
    step_result = StepResult.fromTestFile(test_file)

    self.assertEqual(step_result.master, 'test_master')
    self.assertEqual(step_result.builder_name, 'test_builder_name')
    self.assertEqual(step_result.build_number, 42)
    self.assertEqual(step_result.test_type, 'test_step')
    self.assertEqual(step_result.blink_revision, '54321')
    self.assertEqual(step_result.chromium_revision, 'deadbeef' * 5)
    self.assertEqual(step_result.version, 9)
    self.assertEqual(
        calendar.timegm(step_result.time.utctimetuple()), 1411715603)

    (master_out, test_type_out, json_out) = step_result.toJson()

    self.assertEqual(master_out, 'test_master')
    self.assertEqual(test_type_out, 'test_step')
    self.assertEqual(self._massage_json(copy.deepcopy(self.test_json_1)),
                     self._massage_json(copy.deepcopy(json_out)))

if __name__ == '__main__':
  unittest.main()
