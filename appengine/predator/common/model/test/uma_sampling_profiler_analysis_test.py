# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import urllib

from analysis.test.uma_sampling_profiler_data_test import TEST_DATA
from analysis.type_enums import CrashClient
from analysis.uma_sampling_profiler_data import UMASamplingProfilerData
from common.appengine_testcase import AppengineTestCase
from common.model.uma_sampling_profiler_analysis import (
    UMASamplingProfilerAnalysis)


class UMASamplingProfilerAnalysisTest(AppengineTestCase):
  """Tests ``UMASamplingProfilerAnalysis`` class."""

  def _GetDummyUMASamplingProfilerAnalysis(self):
    """Returns an ``UMASamplingProfilerAnalysis`` with custom fields filled."""
    analysis = UMASamplingProfilerAnalysis()
    analysis.process_type = 'BROWSER_PROCESS'
    analysis.startup_phase = 'MAIN_LOOP_START'
    analysis.thread_type = 'UI_THREAD'
    analysis.collection_trigger = 'PROCESS_STARTUP'
    analysis.subtree_root_depth = 19
    analysis.subtree_id = 'AEF6F487C2EE7935'
    analysis.chrome_releases = [
        {'version': '54.0.2834.0', 'channel': 'canary'},
        {'version': '54.0.2835.0', 'channel': 'canary'}
    ]
    return analysis

  def testUMASamplingProfilerAnalysisReset(self):
    """Tests ``Reset`` reset all properties."""
    analysis = self._GetDummyUMASamplingProfilerAnalysis()
    analysis.Reset()

    self.assertIsNone(analysis.process_type)
    self.assertIsNone(analysis.startup_phase)
    self.assertIsNone(analysis.thread_type)
    self.assertIsNone(analysis.collection_trigger)
    self.assertIsNone(analysis.subtree_root_depth)
    self.assertIsNone(analysis.subtree_id)
    self.assertIsNone(analysis.chrome_releases)
    self.assertIsNone(analysis.subtree_stacks)

  def testInitializeWithRegressionData(self):
    """Tests ``Initialize`` initialize all properties from regression data."""
    predator = self.GetMockPredatorApp()
    raw_regression_data = TEST_DATA

    class MockUMASamplingProfilerData(UMASamplingProfilerData):

      def __init__(self, raw_regression_data):
        super(MockUMASamplingProfilerData, self).__init__(raw_regression_data,
                                                          None)

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
        return_value=MockUMASamplingProfilerData(raw_regression_data))

    regression_data = predator.GetCrashData(raw_regression_data)
    analysis = UMASamplingProfilerAnalysis()
    analysis.Initialize(regression_data)

    self.assertEqual(analysis.process_type, regression_data.process_type)
    self.assertEqual(analysis.startup_phase, regression_data.startup_phase)
    self.assertEqual(analysis.thread_type, regression_data.thread_type)
    self.assertEqual(analysis.collection_trigger,
                     regression_data.collection_trigger)
    self.assertEqual(analysis.subtree_root_depth,
                     regression_data.subtree_root_depth)
    self.assertEqual(analysis.chrome_releases, regression_data.chrome_releases)

  def testClientId(self):
    """Tests the ``client_id`` field."""
    analysis = UMASamplingProfilerAnalysis()
    self.assertEqual(analysis.client_id, CrashClient.UMA_SAMPLING_PROFILER)

  def testCrashUrl(self):
    """Tests that the ``crash_url`` generates correctly."""
    analysis = UMASamplingProfilerAnalysis()
    analysis.chrome_releases = [
        {'version': '54.0.2834.0', 'channel': 'canary'},
        {'version': '54.0.2835.0', 'channel': 'canary'}
    ]
    analysis.process_type = 'BROWSER_PROCESS'
    analysis.subtree_id = 'AEF6F487C2EE7935'

    url = analysis.crash_url

    url_base = 'https://uma.googleplex.com/p/chrome/callstacks?q='
    self.assertTrue(url.startswith(url_base))
    params_string = url[len(url_base):]
    params_dict = json.loads(urllib.unquote(params_string))
    expected_params = {
        'editor': {
            'displayDiff': True,
            'primarySelector': {
                'process': '1',
                'release': '54.0.2835.0 1'
            },
            'secondarySelector': {
                'process': '1',
                'release': '54.0.2834.0 1'
            }
        },
        'visualizer': {
            'flame_view_model': {
                'flame_graph_model': {
                    'zoom_to_node': 'AEF6F487C2EE7935'
                }
            }
        }
    }
    self.assertDictEqual(params_dict, expected_params)

  def testCustomizedData(self):
    """Tests that ``customized_data`` returns the correct fields."""
    analysis = self._GetDummyUMASamplingProfilerAnalysis()
    expected_customized_data = {
        'process_type': analysis.process_type,
        'startup_phase': analysis.startup_phase,
        'thread_type': analysis.thread_type,
        'collection_trigger': analysis.collection_trigger,
        'subtree_root_depth': analysis.subtree_root_depth,
        'subtree_id': analysis.subtree_id,
        'chrome_releases': analysis.chrome_releases,
        'subtree_stacks': analysis.subtree_stacks,
    }

    self.assertDictEqual(analysis.customized_data, expected_customized_data)

  def testToJson(self):
    """Tests that ``ToJson`` returns the correct fields."""
    analysis = self._GetDummyUMASamplingProfilerAnalysis()
    expected_json = {
        'platform': analysis.platform,
        'process_type': analysis.process_type,
        'startup_phase': analysis.startup_phase,
        'thread_type': analysis.thread_type,
        'collection_trigger': analysis.collection_trigger,
        'chrome_releases': analysis.chrome_releases,
        'subtree_root_depth': analysis.subtree_root_depth,
        'subtree_id': analysis.subtree_id,
        'subtree_stacks': analysis.subtree_stacks,
    }

    self.assertDictEqual(analysis.ToJson(), expected_json)

  def testToJsonWithMissingStartupPhase(self):
    """Tests that ``ToJson`` works when ``startup_phase`` field is missing."""
    analysis = self._GetDummyUMASamplingProfilerAnalysis()
    analysis.startup_phase = None
    expected_json = {
        'platform': analysis.platform,
        'process_type': analysis.process_type,
        'thread_type': analysis.thread_type,
        'collection_trigger': analysis.collection_trigger,
        'chrome_releases': analysis.chrome_releases,
        'subtree_root_depth': analysis.subtree_root_depth,
        'subtree_id': analysis.subtree_id,
        'subtree_stacks': analysis.subtree_stacks,
    }

    self.assertDictEqual(analysis.ToJson(), expected_json)
