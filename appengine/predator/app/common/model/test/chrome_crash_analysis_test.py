# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from analysis.chrome_crash_data import ChromeCrashData
from common.appengine_testcase import AppengineTestCase
from common.model.chrome_crash_analysis import ChromeCrashAnalysis


class ChromeCrashAnalysisTest(AppengineTestCase):

  def testDoNotUseIdentifiersToSetProperties(self):
    crash_identifiers = {
      'chrome_version': '1',
      'signature': 'signature/here',
      'channel': 'canary',
      'platform': 'win',
      'process_type': 'browser',
    }
    ChromeCrashAnalysis.Create(crash_identifiers).put()
    analysis = ChromeCrashAnalysis.Get(crash_identifiers)
    self.assertIsNone(analysis.crashed_version)
    self.assertIsNone(analysis.signature)
    self.assertIsNone(analysis.channel)
    self.assertIsNone(analysis.platform)

  def testChromeCrashAnalysisReset(self):
    analysis = ChromeCrashAnalysis()
    analysis.historical_metadata = {}
    analysis.Reset()
    self.assertIsNone(analysis.channel)
    self.assertIsNone(analysis.historical_metadata)

  def testInitializeWithCrashData(self):
    predator = self.GetMockPredatorApp()
    channel = 'dummy channel'
    historical_metadata = []
    crash_data = self.GetDummyChromeCrashData(
        channel=channel, historical_metadata=historical_metadata)

    class MockChromeCrashData(ChromeCrashData):  # pylint: disable=W0223

      def __init__(self, crash_data):
        super(MockChromeCrashData, self).__init__(crash_data, None)

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

    predator.GetCrashData = mock.Mock(
        return_value=MockChromeCrashData(crash_data))

    crash_data = predator.GetCrashData(crash_data)
    analysis = ChromeCrashAnalysis()
    analysis.Initialize(crash_data)
    self.assertEqual(analysis.channel, channel)
    self.assertEqual(analysis.historical_metadata, historical_metadata)

  def testCustomizedData(self):
    """Tests ``customized_data`` property."""
    analysis = ChromeCrashAnalysis()
    analysis.channel = 'dummy channel'
    analysis.historical_metadata = []

    self.assertDictEqual(analysis.customized_data,
                         {'channel': analysis.channel,
                          'historical_metadata': analysis.historical_metadata})

  def testToJson(self):
    historical_metadata = [{'chrome_version': '1'}, {'chrome_version': '2'}]
    channel = 'win'
    expected_json = {
        'channel': channel,
        'historical_metadata': historical_metadata
    }
    analysis = ChromeCrashAnalysis.Create(expected_json)
    analysis.channel = channel
    analysis.historical_metadata = historical_metadata

    self.assertDictEqual(analysis.ToJson(),
                         {'customized_data': expected_json,
                          'platform': None,
                          'stack_trace': None,
                          'chrome_version': None,
                          'signature': None})
