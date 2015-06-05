# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import gzip
import os
import unittest

from common.retry_http_client import RetryHttpClient
from waterfall import buildbot


class DummyHttpClient(RetryHttpClient):

  def __init__(self, status_code, response_content):
    self.status_code = status_code
    self.response_content = response_content
    self.requests = []

  def GetBackoff(self, *_):  # pragma: no cover
    """Override to avoid sleep."""
    return 0

  def _Get(self, url, _):
    self.requests.append(url)
    return self.status_code, self.response_content


class BuildBotTest(unittest.TestCase):
  def testGetMasternameFromUrl(self):
    cases = {
        None: None,
        '': None,
        'https://unknown.host/p/chromium': None,
        'http://build.chromium.org/p/chromium': 'chromium',
        'http://build.chromium.org/p/chromium/builders/Linux': 'chromium',
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
        'http://build.chromium.org/p/chromium/builders/Linux/builds/55833':
            ('chromium', 'Linux', 55833),
        ('http://build.chromium.org/p/chromium.win/builders/'
         'Win7%20Tests%20%281%29/builds/33911'): (
             'chromium.win', 'Win7 Tests (1)', 33911),
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
    expected_url = ('https://build.chromium.org/p/a/builders/'
                    'Win7%20Tests%20%281%29/builds/123')
    expected_url_json = ('https://build.chromium.org/p/a/json/builders/'
                         'Win7%20Tests%20%281%29/builds/123')

    self.assertEqual(
        expected_url,
        buildbot.CreateBuildUrl(master_name, builder_name, build_number))

    self.assertEqual(
        expected_url_json,
        buildbot.CreateBuildUrl(master_name, builder_name, build_number, True))

  def testCreateStdioLogUrl(self):
    master_name = 'a'
    builder_name = 'Win7 Tests (1)'
    build_number = 123
    step_name = '[trigger] abc_tests'
    expected_stdio_log_url = ('https://build.chromium.org/p/a/builders/'
                              'Win7%20Tests%20%281%29/builds/123/steps/'
                              '%5Btrigger%5D%20abc_tests/logs/stdio/text')

    self.assertEqual(
        expected_stdio_log_url,
        buildbot.CreateStdioLogUrl(
            master_name, builder_name, build_number, step_name))

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
    http_client = DummyHttpClient(200, 'abc')
    data = buildbot.GetBuildDataFromArchive(
        master_name, builder_name, build_number, http_client)
    self.assertEqual(http_client.response_content, data)
    self.assertEqual(1, len(http_client.requests))
    self.assertEqual(expected_url, http_client.requests[0])

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
    
  def testGetBuildDataFromBuildMasterSuccess(self):
    master_name = 'a'
    builder_name = 'b c'
    build_number = 1
    expected_url = 'https://build.chromium.org/p/a/json/builders/b%20c/builds/1'
    http_client = DummyHttpClient(200, 'abc')
    data = buildbot.GetBuildDataFromBuildMaster(
        master_name, builder_name, build_number, http_client)
    self.assertEqual(http_client.response_content, data)
    self.assertEqual(1, len(http_client.requests))
    self.assertEqual(expected_url, http_client.requests[0])

  def testGetBuildDataFromBuildMasterFailure(self):
    master_name = 'a'
    builder_name = 'b c'
    build_number = 1
    expected_url = 'https://build.chromium.org/p/a/json/builders/b%20c/builds/1'
    http_client = DummyHttpClient(404, 'Not Found')
    data = buildbot.GetBuildDataFromBuildMaster(
        master_name, builder_name, build_number, http_client)
    self.assertIsNone(data)
    self.assertEqual(1, len(http_client.requests))
    self.assertEqual(expected_url, http_client.requests[0])

  def testGetStepStdioSuccess(self):
    master_name = 'a'
    builder_name = 'b c'
    build_number = 1
    step_name = 'd f'
    expected_url = ('https://build.chromium.org/p/a/builders/b%20c/builds/1/'
                    'steps/d%20f/logs/stdio/text')
    http_client = DummyHttpClient(200, 'abc')
    data = buildbot.GetStepStdio(
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
    data = buildbot.GetStepStdio(
        master_name, builder_name, build_number, step_name, http_client)
    self.assertIsNone(data)
    self.assertEqual(1, len(http_client.requests))
    self.assertEqual(expected_url, http_client.requests[0])

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
    expected_build_start_time = datetime.fromtimestamp(start_time)

    build_start_time = buildbot.GetBuildStartTime({
        'times': [start_time, stop_time]})
    self.assertEqual(expected_build_start_time, build_start_time)

  def testExtractBuildInfo(self):
    build_file = os.path.join(
        os.path.dirname(__file__), 'data', 'sample_build.json')
    with open(build_file, 'r') as f:
      build_data = f.read()

    master_name = 'a'
    builder_name = 'b'
    build_number = 632
    expected_build_start_time = datetime.fromtimestamp(1417470720.763887)
    expected_chromium_revision = '449cdbd05616de91fcf7e8b4282e300336d6d7c5'
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
        'sync_unit_tests',
        'ui_base_unittests',
        'url_unittests',
        'views_unittests',
        'wm_unittests',
        'base_unittests on Windows-XP-SP3',
        'browser_tests on Windows-XP-SP3',
        'content_browsertests on Windows-XP-SP3',
        'content_unittests on Windows-XP-SP3',
    ]

    build_info = buildbot.ExtractBuildInfo(
        master_name, builder_name, build_number, build_data)

    self.assertEqual(master_name, build_info.master_name)
    self.assertEqual(builder_name, build_info.builder_name)
    self.assertEqual(build_number, build_info.build_number)
    self.assertEqual(expected_build_start_time, build_info.build_start_time)
    self.assertEqual(expected_chromium_revision, build_info.chromium_revision)
    self.assertEqual(expected_completed, build_info.completed)
    self.assertEqual(expected_result, build_info.result)
    self.assertEqual(expected_blame_list, build_info.blame_list)
    self.assertEqual(expected_failed_steps, build_info.failed_steps)
    self.assertEqual(expected_passed_steps, build_info.passed_steps)
