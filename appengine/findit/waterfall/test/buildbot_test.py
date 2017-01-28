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

import google

from libs.http.retry_http_client import RetryHttpClient
from waterfall import buildbot
from waterfall.test import wf_testcase

third_party = os.path.join(
  os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
sys.path.insert(0, third_party)
google.__path__.append(os.path.join(third_party, 'google'))
from logdog import annotations_pb2


def _GenerateGetResJson(value):
  data = {
      'logs': [
          {
              'text': {
                  'lines': [
                      {
                          'value': value
                      },
                      {
                          'other': '\n'
                      }
                  ]
              }
          }
      ]
  }
  return json.dumps(data)


_SAMPLE_GET_RESPONSE = _GenerateGetResJson(json.dumps(
  wf_testcase.SAMPLE_STEP_METADATA))


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


def _CreateProtobufMessage(
    step_name, stdout_stream, step_metadata_stream, label='step_metadata'):
  step = annotations_pb2.Step()
  message = step.substep.add().step
  message.name = step_name
  message.stdout_stream.name = stdout_stream
  link = message.other_links.add(label=label)
  link.logdog_stream.name = step_metadata_stream
  return step


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

  def _GenerateTailRes(self):
    step_proto = _CreateProtobufMessage(
      self.step_name, self.stdout_stream, self.step_metadata_stream)
    step_log = step_proto.SerializeToString()
    step_b64 = base64.b64encode(step_log)
    tail_res_json = {
        'logs': [
            {
                'datagram': {
                    'data': step_b64
                }
            }
        ]
    }
    return json.dumps(tail_res_json)

  @mock.patch.object(buildbot, 'DownloadJsonData', return_value=None)
  def testFailToGetRecentCompletedBuilds(self, _):
    self.assertEqual(
      [], buildbot.GetRecentCompletedBuilds('m', 'b', _))

  @mock.patch.object(buildbot, 'DownloadJsonData')
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
        'https://uberchromegw.corp.google.com/i/m1/builders/Linux': 'm1',
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
        'https://uberchromegw.corp.google.com/i/m1/builders/b1/builds/234': (
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

  @mock.patch.object(buildbot, 'DownloadJsonData')
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

  @mock.patch.object(buildbot, '_GetResultJson')
  @mock.patch.object(buildbot, '_DownloadData')
  def testDownloadJsonData(self, mock_fn_1, mock_fn_2):
    mocked_response_json = {'a': 'a'}
    mocked_response = json.dumps(mocked_response_json)
    mock_fn_1.return_value = mocked_response
    mock_fn_2.return_value = mocked_response_json

    url = 'url'
    data = {'data': 'data'}
    http_client = RetryHttpClient()

    response_json = buildbot.DownloadJsonData(url, data, http_client)

    self.assertEqual(response_json, mocked_response_json)
    mock_fn_1.assert_called_once_with(url, data, http_client)
    mock_fn_2.assert_called_once_with(mocked_response)

  def testDownloadDataError(self):
    mocked_http_client = mock.Mock()
    mocked_http_client.Post.return_value = (404, '404')

    url = 'url'
    data = {
        'data': 'data'
    }
    self.assertIsNone(
      buildbot._DownloadData(url, data, mocked_http_client))
    mocked_http_client.assert_has_calls(
      mock.call.Post(
        'url', json.dumps(data),
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json'}))

  def testDownloadData(self):
    response = 'response'
    mocked_http_client = mock.Mock()
    mocked_http_client.Post.return_value = (200, response)

    url = 'url'
    data = {
        'data': 'data'
    }
    self.assertEqual(
      response, buildbot._DownloadData(url, data, mocked_http_client))

  def testGetResultJsonNoPrefix(self):
    response = 'response_json'
    self.assertEqual(response, buildbot._GetResultJson(response))

  def testGetResultJson(self):
    response_json = 'response_json'
    response = '%s%s' % (buildbot._RESPONSE_PREFIX, response_json)
    self.assertEqual(response_json, buildbot._GetResultJson(response))

  def testProcessStringForLogDog(self):
    builder_name = 'Mac 10.10 Release (Intel)'
    expected_builder_name = 'Mac_10.10_Release__Intel_'
    self.assertEqual(expected_builder_name,
                     buildbot._ProcessStringForLogDog(builder_name))

  @mock.patch.object(buildbot, 'DownloadJsonData',
                     return_value=_SAMPLE_GET_RESPONSE)
  def testGetStepMetadataFromLogDog(self, _):
    step_metadata = buildbot._GetLogFromLogDog(
      self.master_name, self.builder_name, self.build_number,
      'stream', self.http_client)
    self.assertEqual(json.loads(step_metadata),
                     wf_testcase.SAMPLE_STEP_METADATA)

  @mock.patch.object(buildbot, 'DownloadJsonData',
                     return_value=None)
  def testGetStepMetadataFromLogDogNoResponse(self, _):
    step_metadata = buildbot._GetLogFromLogDog(
      self.master_name, self.builder_name, self.build_number,
      'stream', self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(buildbot, 'DownloadJsonData',
                     return_value=json.dumps({'a': 'a'}))
  def testGetStepMetadataFromLogDogNoJson(self, _):
    step_metadata = buildbot._GetLogFromLogDog(
      self.master_name, self.builder_name, self.build_number,
      'stream', self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(buildbot, '_GetAnnotationsProto',
                     return_value='step')
  @mock.patch.object(buildbot, '_ProcessAnnotationsToGetStream',
                     return_value='log_stream')
  @mock.patch.object(buildbot, '_GetLogFromLogDog',
                     return_value=json.dumps(wf_testcase.SAMPLE_STEP_METADATA))
  def testGetStepMetadata(self, *_):
    step_metadata = buildbot.GetStepLog(
      self.master_name, self.builder_name, self.build_number, self.step_name,
      self.http_client, 'step_metadata')
    self.assertEqual(step_metadata, wf_testcase.SAMPLE_STEP_METADATA)

  @mock.patch.object(buildbot, '_GetAnnotationsProto',
                     return_value=None)
  def testGetStepMetadataStepNone(self, _):
    step_metadata = buildbot.GetStepLog(
      self.master_name, self.builder_name, self.build_number, self.step_name,
      self.http_client, 'step_metadata')
    self.assertIsNone(step_metadata)

  @mock.patch.object(buildbot, '_GetAnnotationsProto',
                     return_value='step')
  @mock.patch.object(buildbot, '_ProcessAnnotationsToGetStream',
                     return_value=None)
  def testGetStepMetadataStreamNone(self, *_):
    step_metadata = buildbot.GetStepLog(
      self.master_name, self.builder_name, self.build_number, self.step_name,
      self.http_client, 'step_metadata')
    self.assertIsNone(step_metadata)

  def testProcessAnnotationsToGetStreamForStepMetadata(self):
    step_proto = _CreateProtobufMessage(
      self.step_name, self.stdout_stream, self.step_metadata_stream)
    log_stream = buildbot._ProcessAnnotationsToGetStream(
      self.step_name, step_proto, 'step_metadata')
    self.assertEqual(log_stream, self.step_metadata_stream)

  def testProcessAnnotationsToGetStreamForStdout(self):
    step_proto = _CreateProtobufMessage(
      self.step_name, self.stdout_stream, self.step_metadata_stream)
    log_stream = buildbot._ProcessAnnotationsToGetStream(
      self.step_name, step_proto)
    self.assertEqual(log_stream, self.stdout_stream)

  def testProcessAnnotationsToGetStreamNoStep(self):
    step = _CreateProtobufMessage(
      'step', self.stdout_stream, self.step_metadata_stream)
    log_stream = buildbot._ProcessAnnotationsToGetStream(
      self.step_name, step, 'step_metadata')
    self.assertIsNone(log_stream)

  def testProcessAnnotationsToGetStreamNoStepMetadta(self):
    step = _CreateProtobufMessage(
      self.step_name, self.stdout_stream, self.step_metadata_stream, 'step')
    log_stream = buildbot._ProcessAnnotationsToGetStream(
      self.step_name, step, 'step_metadata')
    self.assertIsNone(log_stream)

  @mock.patch.object(buildbot, 'DownloadJsonData')
  def testGetAnnotationsProto(self, mock_fn):
    mock_fn.return_value = self._GenerateTailRes()
    step = buildbot._GetAnnotationsProto(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNotNone(step)

  @mock.patch.object(buildbot, 'DownloadJsonData', return_value=None)
  def testGetAnnotationsProtoNoResponse(self, _):
    step = buildbot._GetAnnotationsProto(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(buildbot, 'DownloadJsonData',
                     return_value=json.dumps({'a': 'a'}))
  def testGetAnnotationsProtoNoLogs(self, _):
    step = buildbot._GetAnnotationsProto(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(buildbot, 'DownloadJsonData')
  def testGetAnnotationsProtoNoAnnotationsB64(self, mock_fn):
    data = {
        'logs': [
            {
                'data': 'data'
            }
        ]
    }
    mock_fn.return_value = json.dumps(data)
    step = buildbot._GetAnnotationsProto(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(buildbot, 'DownloadJsonData')
  def testGetAnnotationsProtoNoB64decodable(self, mock_fn):
    data = {
        'logs': [
            {
                'datagram': {
                    'data': 'data'
                }
            }
        ]
    }
    mock_fn.return_value = json.dumps(data)
    step = buildbot._GetAnnotationsProto(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(buildbot, '_GetAnnotationsProto', return_value='step')
  @mock.patch.object(buildbot, '_ProcessAnnotationsToGetStream',
                     return_value='stream')
  @mock.patch.object(buildbot, '_GetLogFromLogDog', return_value='log1/nlog2')
  def testGetStepLogStdio(self, *_):
    self.assertEqual('log1/nlog2', buildbot.GetStepLog(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        self.http_client))
