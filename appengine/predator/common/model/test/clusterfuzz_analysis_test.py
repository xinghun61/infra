# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from analysis.clusterfuzz_data import ClusterfuzzData
from analysis.type_enums import CrashClient
from common.appengine_testcase import AppengineTestCase
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis


class ClusterfuzzAnalysisTest(AppengineTestCase):
  """Tests ``ClusterfuzzAnalysis`` class."""

  def testClusterfuzzAnalysisReset(self):
    """Tests ``Reset`` reset all properties."""
    analysis = ClusterfuzzAnalysis()
    analysis.crashed_type = 'check'
    analysis.crash_address = '0x0000'
    analysis.sanitizer = 'ASAN'
    analysis.job_type = 'android_asan_win'
    analysis.Reset()
    self.assertIsNone(analysis.crashed_type)
    self.assertIsNone(analysis.crashed_address)
    self.assertIsNone(analysis.sanitizer)
    self.assertIsNone(analysis.job_type)

  def testInitializeWithCrashData(self):
    """Tests ``Initialize`` initialize all properties from crash data."""
    findit = self.GetMockFindit()
    raw_crash_data = self.GetDummyClusterfuzzData()
    class MockClusterfuzzData(ClusterfuzzData):

      def __init__(self, raw_crash_data):
        super(MockClusterfuzzData, self).__init__(raw_crash_data, None)

      @property
      def stacktrace(self):
        return None

      @property
      def regression_range(self):
        return None

      @property
      def dependencies(self):
        return {}

      @property
      def dependency_rolls(self):
        return {}

    self.mock(findit, 'GetCrashData',
              lambda raw_crash_data:  # pylint: disable=W0108
              MockClusterfuzzData(raw_crash_data))

    crash_data = findit.GetCrashData(raw_crash_data)
    analysis = ClusterfuzzAnalysis()
    analysis.Initialize(crash_data)
    self.assertEqual(analysis.crashed_type, crash_data.crashed_type)
    self.assertEqual(analysis.crashed_address, crash_data.crashed_address)
    self.assertEqual(analysis.job_type, crash_data.job_type)
    self.assertEqual(analysis.sanitizer, crash_data.sanitizer)

  def testProperties(self):
    testcase = '1232435'

    analysis = ClusterfuzzAnalysis.Create(testcase)
    analysis.testcase = testcase

    self.assertEqual(analysis.identifiers, testcase)

  def testToJson(self):
    testcase = '1234'
    job_type = 'asan'
    analysis = ClusterfuzzAnalysis.Create(testcase)
    analysis.testcase = testcase
    analysis.job_type = job_type

    expected_json = {
        'regression_range': None,
        'dependencies': None,
        'dependency_rolls': None,
        'crashed_type': None,
        'crashed_address': None,
        'sanitizer': None,
        'job_type': job_type,
        'testcase': testcase
    }

    self.assertDictEqual(analysis.ToJson(),
                         {'customized_data': expected_json,
                          'platform': None,
                          'stack_trace': None,
                          'chrome_version': None,
                          'signature': None})
