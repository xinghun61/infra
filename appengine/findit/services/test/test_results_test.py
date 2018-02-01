# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from services import gtest
from services import test_results
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class TestResultsTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      gtest, 'IsTestResultsInExpectedFormat', return_value=False)
  def testGetTestResultObjectNoMatch(self, _):
    self.assertIsNone(test_results._GetTestResultObject('log'))

  @mock.patch.object(
      gtest, 'IsTestResultsInExpectedFormat', return_value=True)
  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask')
  def testIsTestEnabled(self, isolate_fn, _):
    test_name = 'test'
    isolate_fn.return_value = {'all_tests': ['test'], 'disabled_tests': []}
    self.assertTrue(test_results.IsTestEnabled(test_name, {'all_tests': []}))

  def testRetrieveShardedTestResultsFromIsolatedServerNoLog(self):
    self.assertEqual([],
                     test_results.RetrieveShardedTestResultsFromIsolatedServer(
                         [], None))

  @mock.patch.object(
      gtest, 'IsTestResultsInExpectedFormat', return_value=True)
  @mock.patch.object(swarming_util, 'DownloadTestResults')
  def testRetrieveShardedTestResultsFromIsolatedServer(self, mock_data, _):
    isolated_data = [{
        'digest':
            'shard1_isolated',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }, {
        'digest':
            'shard2_isolated',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }]

    mock_data.side_effect = [({
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test1': [{
                'output_snippet': '[ RUN ] test1.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }, 200), ({
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test2': [{
                'output_snippet': '[ RUN ] test2.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }, 200)]
    result = test_results.RetrieveShardedTestResultsFromIsolatedServer(
        isolated_data, None)
    expected_result = {
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test1': [{
                'output_snippet': '[ RUN ] test1.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }],
            'test2': [{
                'output_snippet': '[ RUN ] test2.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }

    self.assertEqual(expected_result, result)

  @mock.patch.object(
      gtest, 'IsTestResultsInExpectedFormat', return_value=True)
  @mock.patch.object(swarming_util, 'DownloadTestResults')
  def testRetrieveShardedTestResultsFromIsolatedServerOneShard(
      self, mock_data, _):
    isolated_data = [{
        'digest':
            'shard1_isolated',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }]
    data = {'all_tests': ['test'], 'per_iteration_data': []}
    mock_data.return_value = (data, 200)

    result = test_results.RetrieveShardedTestResultsFromIsolatedServer(
        isolated_data, None)

    self.assertEqual(data, result)

  @mock.patch.object(
      gtest, 'IsTestResultsInExpectedFormat', return_value=True)
  @mock.patch.object(swarming_util, 'DownloadTestResults')
  def testRetrieveShardedTestResultsFromIsolatedServerFailed(
      self, mock_data, _):
    isolated_data = [{
        'digest':
            'shard1_isolated',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }]
    mock_data.return_value = (None, 404)

    result = test_results.RetrieveShardedTestResultsFromIsolatedServer(
        isolated_data, None)

    self.assertIsNone(result)
