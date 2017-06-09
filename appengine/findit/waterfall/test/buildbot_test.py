# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from datetime import datetime
import gzip
import io
import json
import mock
import os
import sys
import unittest
import urllib

import google

from common import rpc_util
from infra_api_clients import logdog_util
from libs.http.retry_http_client import RetryHttpClient
from waterfall import buildbot
from waterfall.test import wf_testcase


class DummyHttpClient(RetryHttpClient):
  def __init__(self, status_code, response_content):
    self.status_code = status_code
    self.response_content = response_content
    self.requests = []

  def GetBackoff(self, *_):  # pragma: no cover
    """Override to avoid sleep."""
    return 0

  def _Get(self, url, *_):
    self.requests.append(url)
    return self.status_code, self.response_content

  def _Post(self, *_):  # pragma: no cover
    pass

  def _Put(self, *_):  # pragma: no cover
    pass


class BuildBotTest(unittest.TestCase):
  def setUp(self):
    super(BuildBotTest, self).setUp()
    self.http_client = RetryHttpClient()
    self.master_name = 'tryserver.m'
    self.wf_master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 123
    self.step_name = 'browser_tests on platform'

    self.stdout_stream = 'stdout_stream'
    self.step_metadata_stream = 'step_metadata_stream'

  @mock.patch.object(rpc_util, 'DownloadJsonData', return_value=None)
  def testFailToGetRecentCompletedBuilds(self, _):
    self.assertEqual(
      [], buildbot.GetRecentCompletedBuilds('m', 'b', _))

  @mock.patch.object(buildbot, '_GetMasterJsonData')
  def testListBuildersOnMaster(self, mocked_fn):
    mocked_fn.return_value = json.dumps({
        'builders': {
            'builder_1': {},
            'builder_2': {}
        }})

    self.assertEqual(
        ['builder_1', 'builder_2'],
        buildbot.ListBuildersOnMaster('master', RetryHttpClient()))

  @mock.patch.object(buildbot, '_GetMasterJsonData', return_value=None)
  def testListBuildersOnMasterError(self, _):
    self.assertEqual(
        [],
        buildbot.ListBuildersOnMaster('master', RetryHttpClient()))

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetRecentCompletedBuilds(self, mock_fn):
    builders_data = {
        'builders': {
            'b': {
                'cachedBuilds': [33, 32, 34, 35],
                'currentBuilds': [35]
            }
        }
    }

    builders_json_data = json.dumps(builders_data)
    compressed_file = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_file, mode='w') as compressed:
      compressed.write(builders_json_data)

    data = {
      'data': base64.b64encode(compressed_file.getvalue())
    }
    compressed_file.close()
    mock_fn.return_value = json.dumps(data)
    self.assertEqual(
      [34, 33, 32],
      buildbot.GetRecentCompletedBuilds('m', 'b', RetryHttpClient()))

  def testGetMasternameFromUrl(self):
    cases = {
        None: None,
        '': None,
        'https://unknown.host/p/chromium': None,
        'http://build.chromium.org/p/chromium': 'chromium',
        'http://build.chromium.org/p/chromium/builders/Linux': 'chromium',
        'https://abc.def.google.com/i/m1/builders/Linux': 'm1',
        'https://luci-milo.appspot.com/buildbot/m2/b/123': 'm2',
    }

    for url, expected_result in cases.iteritems():
      result = buildbot.GetMasterNameFromUrl(url)
      self.assertEqual(expected_result, result)

  def testParseBuildUrl(self):
    cases = {
        None: None,
        '': None,
        'https://unknown.host/p/chromium/builders/Linux/builds/55833': None,
        'http://build.chromium.org/p/chromium/builders/Linux': None,
        'http://build.chromium.org/p/chromium/builders/Linux/builds/55833': (
            'chromium', 'Linux', 55833),
        ('http://build.chromium.org/p/chromium.win/builders/'
         'Win7%20Tests%20%281%29/builds/33911'): (
             'chromium.win', 'Win7 Tests (1)', 33911),
        'https://abc.def.google.com/i/m1/builders/b1/builds/234': (
            'm1', 'b1', 234),
        'https://luci-milo.appspot.com/buildbot/m2/b2/123': ('m2', 'b2', 123),
    }

    for url, expected_result in cases.iteritems():
      result = buildbot.ParseBuildUrl(url)
      self.assertEqual(expected_result, result)

  def testParseStepUrl(self):
    cases = {
        None: None,
        '': None,
        ('https://unknown_host/p/chromium/builders/Linux/builds/55833/'
         '/steps/compile'): None,
        'http://build.chromium.org/p/chromium/builders/Linux': None,
        ('http://build.chromium.org/p/chromium/builders/Linux/builds/55833'
         '/steps/compile'): (
             'chromium', 'Linux', 55833, 'compile'),
        ('http://build.chromium.org/p/chromium.win/builders/Win7%20Tests%20'
         '%281%29/builds/33911/steps/interactive_ui'): (
             'chromium.win', 'Win7 Tests (1)', 33911, 'interactive_ui'),
    }

    for url, expected_result in cases.iteritems():
      result = buildbot.ParseStepUrl(url)
      self.assertEqual(expected_result, result)

  def testCreateArchivedBuildUrl(self):
    master_name = 'a'
    builder_name = 'Win7 Tests (1)'
    build_number = 123
    expected_url = ('https://chrome-build-extract.appspot.com/p/a/builders/'
                    'Win7%20Tests%20%281%29/builds/123?json=1')

    self.assertEqual(
      expected_url,
      buildbot.CreateArchivedBuildUrl(master_name,
                                      builder_name,
                                      build_number))

  def testCreateBuildUrl(self):
    master_name = 'a'
    builder_name = 'Win7 Tests (1)'
    build_number = 123
    expected_url = ('https://luci-milo.appspot.com/buildbot/a/'
                    'Win7%20Tests%20%281%29/123')
    self.assertEqual(
      expected_url,
      buildbot.CreateBuildUrl(master_name, builder_name, build_number))

  def testCreateGtestResultPath(self):
    master_name = 'a'
    builder_name = 'Win7 Tests (1)'
    build_number = 123
    step_name = '[trigger] abc_tests'
    expected_stdio_log_url = ('/chrome-gtest-results/buildbot/a/Win7 Tests '
                              '(1)/123/[trigger] abc_tests.json.gz')

    self.assertEqual(
      expected_stdio_log_url,
      buildbot.CreateGtestResultPath(
        master_name, builder_name, build_number, step_name))

  def testGetBuildDataFromArchiveSuccess(self):
    master_name = 'a'
    builder_name = 'b c'
    build_number = 1
    expected_url = ('https://chrome-build-extract.appspot.com/p/a/builders/'
                    'b%20c/builds/1?json=1')
    http_client = mock.create_autospec(RetryHttpClient)
    http_client.Get.return_value = (200, 'abc')
    data = buildbot.GetBuildDataFromArchive(
      master_name, builder_name, build_number, http_client)
    self.assertEqual('abc', data)
    http_client.assert_has_calls([mock.call.Get(expected_url)])

  def testGetBuildDataFromArchiveFailure(self):
    master_name = 'a'
    builder_name = 'b c'
    build_number = 1
    expected_url = ('https://chrome-build-extract.appspot.com/p/a/builders/'
                    'b%20c/builds/1?json=1')
    http_client = DummyHttpClient(404, 'Not Found')
    data = buildbot.GetBuildDataFromArchive(
      master_name, builder_name, build_number, http_client)
    self.assertIsNone(data)
    self.assertEqual(1, len(http_client.requests))
    self.assertEqual(expected_url, http_client.requests[0])

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetBuildDataFromBuildMasterSuccess(self, mock_fn):
    master_name = 'a'
    builder_name = 'b c'
    build_number = 1

    response = {
      'data': base64.b64encode('response')
    }
    mock_fn.return_value = json.dumps(response)

    self.assertEqual('response',
                     buildbot.GetBuildDataFromBuildMaster(
                         master_name, builder_name, build_number,
                         self.http_client))

  def testGetBuildProperty(self):
    properties = [
        ['blamelist', ['test@chromium.org'], 'Build'],
        ['branch', 'master', 'Build'],
        ['got_revision', 'aef91789474be4c6a6ff2b8199be3d56063c0555',
         'Annotation(bot_update)'],
        ['a', 'b', 'c'],
    ]
    property_name = 'got_revision'
    property_value = 'aef91789474be4c6a6ff2b8199be3d56063c0555'

    self.assertEqual(property_value,
                     buildbot.GetBuildProperty(properties, property_name))

    self.assertEqual(None,
                     buildbot.GetBuildProperty(properties, 'Unknown_property'))

  def testGetBuildStartTimeWhenNoTimesAvailable(self):
    self.assertEqual(None, buildbot.GetBuildStartTime({}))

  def testGetBuildStartTimeWhenStartStopTimesAvailable(self):
    start_time = 1417470720.763887
    stop_time = 1417570720.763887
    expected_build_start_time = datetime.utcfromtimestamp(start_time)

    build_start_time = buildbot.GetBuildStartTime({
      'times': [start_time, stop_time]})
    self.assertEqual(expected_build_start_time, build_start_time)

  def testExtractBuildInfoOfRunningBuild(self):
    build_file = os.path.join(
      os.path.dirname(__file__), 'data', 'running_build.json')
    with open(build_file, 'r') as f:
      build_data = f.read()

    master_name = 'a'
    builder_name = 'b'
    build_number = 632
    expected_build_start_time = datetime.utcfromtimestamp(1417470720.763887)
    expected_chromium_revision = '449cdbd05616de91fcf7e8b4282e300336d6d7c5'
    expected_commit_position = 306253
    expected_completed = False
    expected_result = None
    expected_blame_list = [
        'f1e24ae21c95228522c24697dae474db5f26854b',
        'fae4955b2ae9cf68aa2a391a7640b1c3276656e8',
        '4ef763a9bb3dc53c7afccbcab9a1b0327b83681c',
        '89ef2ae2a6e2d21813c14471eb444c8651b46651',
        '58becfc708670659119ca72472d1d0882797f706',
        '1cc47034de564d0fd33a89c7d785a539b6c3a5a0',
        '87be98a1f687d430c4e1e1a5da04065067a4c1cc',
        '2fa8736ff6af5bc1f4fa0dc5cd7ff356fa24242b',
        '6addffac2601ab1083a55d085847d9bf8e66da02',
        '6bbd1fe6fe674d32d19f44c2c0f7f4f735e0b20e',
        'd7777f96f98668918102861a262b311ae8c8bd74',
        '6b0dcfd9761235e93b45fa9ee9d90474c12adb11',
        '6157b49795f3dfb89220ed72861a114e24f6c0d8',
        '449cdbd05616de91fcf7e8b4282e300336d6d7c5'
    ]
    expected_failed_steps = [
        'interactive_ui_tests on Windows-XP-SP3'
    ]
    expected_passed_steps = [
        'update_scripts',
        'setup_build',
        'taskkill',
        'bot_update',
        'swarming.py --version',
        'read test spec',
        'get compile targets for scripts',
        'cleanup_temp',
        'rmtree build directory',
        'extract build',
        'start_crash_service',
        '[trigger] base_unittests on Windows-XP-SP3',
        '[trigger] browser_tests on Windows-XP-SP3',
        '[trigger] content_browsertests on Windows-XP-SP3',
        '[trigger] content_unittests on Windows-XP-SP3',
        '[trigger] interactive_ui_tests on Windows-XP-SP3',
        '[trigger] net_unittests on Windows-XP-SP3',
        '[trigger] sync_integration_tests on Windows-XP-SP3',
        '[trigger] unit_tests on Windows-XP-SP3',
        'telemetry_unittests',
        'telemetry_perf_unittests',
        'nacl_integration',
        'accessibility_unittests',
        'app_shell_browsertests',
        'app_shell_unittests',
        'aura_unittests',
        'cacheinvalidation_unittests',
        'cast_unittests',
        'cc_unittests',
        'chromedriver_unittests',
        'chrome_elf_unittests',
        'components_unittests',
        'compositor_unittests',
        'courgette_unittests',
        'crypto_unittests',
        'events_unittests',
        'extensions_unittests',
        'gcm_unit_tests',
        'gfx_unittests',
        'google_apis_unittests',
        'gpu_unittests',
        'installer_util_unittests',
        'ipc_tests',
        'jingle_unittests',
        'media_unittests',
        'ppapi_unittests',
        'printing_unittests',
        'remoting_unittests',
        'sbox_unittests',
        'sbox_integration_tests',
        'sbox_validation_tests',
        'sql_unittests',
        'ui_base_unittests',
        'url_unittests',
        'views_unittests',
        'wm_unittests',
        'base_unittests on Windows-XP-SP3',
        'browser_tests on Windows-XP-SP3',
        'content_browsertests on Windows-XP-SP3',
        'content_unittests on Windows-XP-SP3',
    ]
    expected_not_passed_steps = [
        'interactive_ui_tests on Windows-XP-SP3',
        'net_unittests on Windows-XP-SP3',
    ]

    build_info = buildbot.ExtractBuildInfo(
      master_name, builder_name, build_number, build_data)

    self.assertEqual(master_name, build_info.master_name)
    self.assertEqual(builder_name, build_info.builder_name)
    self.assertEqual(build_number, build_info.build_number)
    self.assertEqual(expected_build_start_time, build_info.build_start_time)
    self.assertEqual(expected_chromium_revision, build_info.chromium_revision)
    self.assertEqual(expected_commit_position, build_info.commit_position)
    self.assertEqual(expected_completed, build_info.completed)
    self.assertEqual(expected_result, build_info.result)
    self.assertEqual(expected_blame_list, build_info.blame_list)
    self.assertEqual(expected_failed_steps, build_info.failed_steps)
    self.assertEqual(expected_passed_steps, build_info.passed_steps)
    self.assertEqual(expected_not_passed_steps, build_info.not_passed_steps)

  def testExtractBuildInfoOfCompletedBuild(self):
    build_file = os.path.join(
      os.path.dirname(__file__), 'data', 'completed_build.json')
    with open(build_file, 'r') as f:
      build_data = f.read()

    master_name = 'a'
    builder_name = 'b'
    build_number = 632
    expected_build_start_time = datetime.utcfromtimestamp(1417470720.763887)
    expected_chromium_revision = '449cdbd05616de91fcf7e8b4282e300336d6d7c5'
    expected_commit_position = 306253
    expected_completed = True
    expected_result = None
    expected_blame_list = [
        '449cdbd05616de91fcf7e8b4282e300336d6d7c5'
    ]
    expected_failed_steps = [
        'net_unittests on Windows-XP-SP3'
    ]
    expected_passed_steps = [
        'browser_tests on Windows-XP-SP3'
    ]
    expected_not_passed_steps = [
        'steps',
        'net_unittests on Windows-XP-SP3',
    ]

    build_info = buildbot.ExtractBuildInfo(
      master_name, builder_name, build_number, build_data)

    self.assertEqual(master_name, build_info.master_name)
    self.assertEqual(builder_name, build_info.builder_name)
    self.assertEqual(build_number, build_info.build_number)
    self.assertEqual(expected_build_start_time, build_info.build_start_time)
    self.assertEqual(expected_chromium_revision, build_info.chromium_revision)
    self.assertEqual(expected_commit_position, build_info.commit_position)
    self.assertEqual(expected_completed, build_info.completed)
    self.assertEqual(expected_result, build_info.result)
    self.assertEqual(expected_blame_list, build_info.blame_list)
    self.assertEqual(expected_failed_steps, build_info.failed_steps)
    self.assertEqual(expected_passed_steps, build_info.passed_steps)
    self.assertEqual(expected_not_passed_steps, build_info.not_passed_steps)

  def testExtractBuildInfoBlameList(self):
    build_file = os.path.join(
      os.path.dirname(__file__), 'data', 'blame_list_test.json')
    with open(build_file, 'r') as f:
      build_data = f.read()

    master_name = 'a'
    builder_name = 'b'
    build_number = 632

    expected_blame_list = [
        '449cdbd05616de91fcf7e8b4282e300336d6d7c5',
        '6addffac2601ab1083a55d085847d9bf8e66da02'
    ]

    build_info = buildbot.ExtractBuildInfo(
      master_name, builder_name, build_number, build_data)

    self.assertEqual(expected_blame_list, build_info.blame_list)

  def testGetCommitPosition(self):
    self.assertIsNone(buildbot._GetCommitPosition(None))
    self.assertIsNone(buildbot._GetCommitPosition(''))
    self.assertIsNone(buildbot._GetCommitPosition('not a commit position'))
    self.assertEqual(
      438538, buildbot._GetCommitPosition('refs/heads/master@{#438538}'))

  @mock.patch.object(logdog_util, '_GetAnnotationsProtoForPath',
                     return_value='step')
  @mock.patch.object(logdog_util, '_GetStreamForStep',
                     return_value='log_stream')
  @mock.patch.object(logdog_util, 'GetStepLogLegacy',
                     return_value=json.dumps(wf_testcase.SAMPLE_STEP_METADATA))
  def testGetStepMetadata(self, *_):
    step_metadata = buildbot.GetStepLog(
      self.master_name, self.builder_name, self.build_number, self.step_name,
      self.http_client, 'step_metadata')
    self.assertEqual(step_metadata, wf_testcase.SAMPLE_STEP_METADATA)

  @mock.patch.object(logdog_util, '_GetAnnotationsProtoForPath',
                     return_value=None)
  def testGetStepMetadataStepNone(self, _):
    step_metadata = buildbot.GetStepLog(
      self.master_name, self.builder_name, self.build_number, self.step_name,
      self.http_client, 'step_metadata')
    self.assertIsNone(step_metadata)

  @mock.patch.object(logdog_util, '_GetAnnotationsProtoForPath',
                     return_value='step')
  @mock.patch.object(logdog_util, '_GetStreamForStep',
                     return_value=None)
  def testGetStepMetadataStreamNone(self, *_):
    step_metadata = buildbot.GetStepLog(
      self.master_name, self.builder_name, self.build_number, self.step_name,
      self.http_client, 'step_metadata')
    self.assertIsNone(step_metadata)

  def testCreateStdioLogUrl(self):
    master_name = 'a'
    builder_name = urllib.quote('Win7 Tests (1)')
    build_number = 123
    step_name = urllib.quote('[trigger] abc_tests')
    expected_stdio_log_url = ('https://build.chromium.org/p/a/builders/'
                              'Win7%20Tests%20%281%29/builds/123/steps/'
                              '%5Btrigger%5D%20abc_tests/logs/stdio/text')

    self.assertEqual(
        expected_stdio_log_url,
        buildbot._CreateStdioLogUrl(
            master_name, builder_name, build_number, step_name))

  def testGetStepStdioSuccess(self):
    master_name = 'a'
    builder_name = 'b c'
    build_number = 1
    step_name = 'd f'
    expected_url = ('https://build.chromium.org/p/a/builders/b%20c/builds/1/'
                    'steps/d%20f/logs/stdio/text')
    http_client = DummyHttpClient(200, 'abc')
    data = buildbot._GetStepStdioFromBuildBot(
        master_name, builder_name, build_number, step_name, http_client)
    self.assertEqual(http_client.response_content, data)
    self.assertEqual(1, len(http_client.requests))
    self.assertEqual(expected_url, http_client.requests[0])

  def testGetStepStdioFailure(self):
    master_name = 'a'
    builder_name = 'b c'
    build_number = 1
    step_name = 'd f'
    expected_url = ('https://build.chromium.org/p/a/builders/b%20c/builds/1/'
                    'steps/d%20f/logs/stdio/text')
    http_client = DummyHttpClient(404, 'Not Found')
    data = buildbot._GetStepStdioFromBuildBot(
        master_name, builder_name, build_number, step_name, http_client)
    self.assertIsNone(data)
    self.assertEqual(1, len(http_client.requests))
    self.assertEqual(expected_url, http_client.requests[0])

  @mock.patch.object(logdog_util, '_GetAnnotationsProtoForPath',
                     return_value='step')
  @mock.patch.object(logdog_util, '_GetStreamForStep',
                     return_value='stream')
  @mock.patch.object(logdog_util, 'GetStepLogLegacy', return_value='log1/nlog2')
  def testGetStepLogStdio(self, *_):
    self.assertEqual('log1/nlog2', buildbot.GetStepLog(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        self.http_client))


  @mock.patch.object(logdog_util, '_GetAnnotationsProtoForPath',
                     return_value=None)
  @mock.patch.object(buildbot, '_GetStepStdioFromBuildBot',
                     return_value='log1/nlog2')
  def testGetStepLogStdioIfNoProto(self, *_):
    self.assertEqual('log1/nlog2', buildbot.GetStepLog(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        self.http_client))

  @mock.patch.object(logdog_util, '_GetAnnotationsProtoForPath',
                     return_value='step')
  @mock.patch.object(logdog_util, '_GetStreamForStep',
                     return_value=None)
  @mock.patch.object(buildbot, '_GetStepStdioFromBuildBot',
                     return_value='log1/nlog2')
  def testGetStepLogStdioIfNoStream(self, *_):
    self.assertEqual('log1/nlog2', buildbot.GetStepLog(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        self.http_client))

  def testGetSwarmingTaskIdFromUrl(self):
    swarm_url = 'https://luci-milo.appspot.com/swarming/task/3595be5002f4bc10'
    non_swarm_url = ('https://luci-milo.appspot.com/buildbot/chromium.linux'
                     '/Linux%20Builder/82087')

    self.assertEqual('3595be5002f4bc10',
                     buildbot.GetSwarmingTaskIdFromUrl(swarm_url))
    self.assertIsNone(buildbot.GetSwarmingTaskIdFromUrl(non_swarm_url))
