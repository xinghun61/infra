# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from crash.clusterfuzz_data import ClusterfuzzData
from crash.test.predator_testcase import PredatorTestCase
from crash.type_enums import CrashClient
from libs import analysis_status
from model import result_status
from model.crash.clusterfuzz_analysis import ClusterfuzzAnalysis


class ClusterfuzzAnalysisTest(PredatorTestCase):
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
