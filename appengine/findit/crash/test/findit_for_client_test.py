# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json

from google.appengine.api import app_identity

from common import git_repository
from crash import detect_regression_range
from crash import findit_for_client
from crash import findit_for_chromecrash
from crash.chromecrash_parser import ChromeCrashParser
from crash.test.crash_testcase import CrashTestCase
from crash.type_enums import CrashClient
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class FinditForClientTest(CrashTestCase):

  def testCheckPolicyUnsupportedClient(self):
    pass_check, _ = findit_for_client.CheckPolicyForClient(
        {'signature': 'sig'}, '1', 'sig', 'unsupported_client',
        'canary', 'stack_trace', {'channel': 'canary'})
    self.assertFalse(pass_check)

  def testCheckPolicyUnsupportedPlatform(self):
    chrome_version = '1'
    signature = 'signature'
    platform = 'unsupported_platform'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': 'canary',
      'platform': platform,
      'process_type': 'browser',
    }

    pass_check, _ = findit_for_client.CheckPolicyForClient(
        crash_identifiers, chrome_version, signature,
        CrashClient.FRACAS, platform, 'stack_trace', {'channel': 'canary'})
    self.assertFalse(pass_check)

  def testCheckPolicyBlacklistedSignature(self):
    chrome_version = '1'
    signature = 'Blacklist marker signature'
    platform = 'win'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': 'canary',
      'platform': platform,
      'process_type': 'browser',
    }

    pass_check, _ = findit_for_client.CheckPolicyForClient(
        crash_identifiers, chrome_version, signature,
        CrashClient.FRACAS, platform, 'stack_trace', {'channel': 'canary'})
    self.assertFalse(pass_check)

  def testCheckPolicyPlatformRename(self):
    chrome_version = '1'
    signature = 'signature'
    platform = 'linux'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': 'canary',
      'platform': platform,
      'process_type': 'browser',
    }

    pass_check, args = findit_for_client.CheckPolicyForClient(
        crash_identifiers, chrome_version, signature,
        CrashClient.FRACAS, platform, 'stack_trace', {'channel': 'canary'})
    self.assertTrue(pass_check)
    self.assertEqual(args[4], 'unix')

  def testGetAnalysisForClient(self):
    crash_identifiers = {'signature': 'sig'}
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.put()

    self.assertEqual(findit_for_client.GetAnalysisForClient(
        crash_identifiers, CrashClient.FRACAS), analysis)

  def testGetAnalysisForUnsuportedClient(self):
    crash_identifiers = {'signature': 'sig'}
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.put()

    self.assertIsNone(findit_for_client.GetAnalysisForClient(
        crash_identifiers, 'Unsupported_client'), analysis)

  def testResetAnalysisForFracas(self):
    chrome_version = '1'
    signature = 'signature'
    platform = 'linux'
    stack_trace = 'stack_trace'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': 'canary',
      'platform': platform,
      'process_type': 'browser',
    }
    customized_data = {'channel': 'canary'}
    regression_range = ['53.0.1235.1', '53.0.1235.1']

    analysis = FracasCrashAnalysis.Create(crash_identifiers)

    findit_for_client.ResetAnalysis(
        analysis, chrome_version, signature, CrashClient.FRACAS, platform,
        stack_trace, customized_data, regression_range)

    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis.crashed_version, chrome_version)
    self.assertEqual(analysis.signature, signature)
    self.assertEqual(analysis.platform, platform)
    self.assertEqual(analysis.stack_trace, stack_trace)
    self.assertEqual(analysis.channel, customized_data['channel'])
    self.assertEqual(analysis.regression_range, regression_range)

  def testCreateAnalysisForClient(self):
    crash_identifiers = {'signature': 'sig'}
    self.assertIsNotNone(findit_for_client.CreateAnalysisForClient(
        crash_identifiers, CrashClient.FRACAS))

  def testCreateAnalysisForUnsupportedClientId(self):
    crash_identifiers = {'signature': 'sig'}
    self.assertIsNone(findit_for_client.CreateAnalysisForClient(
        crash_identifiers, 'unsupported_id'))

  def testGetPublishResultFromAnalysisFoundTrue(self):
    mock_host = 'https://host.com'
    self.mock(app_identity, 'get_default_version_hostname', lambda: mock_host)

    analysis_result = {
        'found': True,
        'suspected_cls': [
            {'confidence': 0.21434,
             'reason': ['reason1', 'reason2'],
             'other': 'data'}
        ],
        'other_data': 'data',
    }

    processed_analysis_result = copy.deepcopy(analysis_result)
    processed_analysis_result['feedback_url'] = (
        mock_host + '/crash/fracas-result-feedback?'
        'key=agx0ZXN0YmVkLXRlc3RyQQsSE0ZyYWNhc0NyYXNoQW5hbHlzaXMiKDMzNTY5MDU3'
        'M2ZlYTFlZGZhMjViOTVjZmI4OGZhODFlNDk0YTEyODkM')

    for cl in processed_analysis_result['suspected_cls']:
      cl['confidence'] = round(cl['confidence'], 2)
      cl.pop('reason', None)

    crash_identifiers = {'signature': 'sig'}
    expected_messages_data = {
            'crash_identifiers': crash_identifiers,
            'client_id': CrashClient.FRACAS,
            'result': processed_analysis_result,
    }

    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.client_id = CrashClient.FRACAS
    analysis.result = analysis_result

    self.assertEqual(findit_for_client.GetPublishResultFromAnalysis(
        analysis, crash_identifiers,
        CrashClient.FRACAS), expected_messages_data)

  def testGetPublishResultFromAnalysisFoundFalse(self):
    mock_host = 'https://host.com'
    self.mock(app_identity, 'get_default_version_hostname', lambda: mock_host)

    analysis_result = {
        'found': False,
    }

    processed_analysis_result = copy.deepcopy(analysis_result)
    processed_analysis_result['feedback_url'] = (
        mock_host + '/crash/fracas-result-feedback?'
        'key=agx0ZXN0YmVkLXRlc3RyQQsSE0ZyYWNhc0NyYXNoQW5hbHlzaXMiKDMzNTY5MDU3'
        'M2ZlYTFlZGZhMjViOTVjZmI4OGZhODFlNDk0YTEyODkM')

    crash_identifiers = {'signature': 'sig'}
    expected_messages_data = {
            'crash_identifiers': crash_identifiers,
            'client_id': CrashClient.FRACAS,
            'result': processed_analysis_result,
    }

    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.client_id = CrashClient.FRACAS
    analysis.result = analysis_result

    self.assertEqual(findit_for_client.GetPublishResultFromAnalysis(
        analysis, crash_identifiers,
        CrashClient.FRACAS), expected_messages_data)

  def testFindCulprit(self):
    expected_result = {'found': False}
    expected_tags = {'found_suspects': False,
                     'has_regression_range': False}

    class _MockFinditForChromeCrash(object):
      def __init__(self, *_):
        pass
      def FindCulprit(self, *_):
        return expected_result, expected_tags
    self.mock(findit_for_chromecrash, 'FinditForChromeCrash',
              _MockFinditForChromeCrash)

    analysis = FracasCrashAnalysis.Create({'signature': 'sig'})
    analysis.client_id = CrashClient.FRACAS

    repository = git_repository.GitRepository()
    result, tags = findit_for_client.FindCulprit(analysis, repository)
    self.assertEqual(result, expected_result)
    self.assertEqual(tags, expected_tags)

    analysis.client_id = 'unsupported_client'
    result, tags = findit_for_client.FindCulprit(analysis, repository)
    self.assertEqual(result, expected_result)
    self.assertEqual(tags, expected_tags)


  def testGetRegressionRange(self):
    expected_regression_range = ['51.0.1233.1', '51.0.1233.2']
    def _MockDetectRegressionRange(*_):
      return expected_regression_range

    self.mock(detect_regression_range, 'DetectRegressionRange',
              _MockDetectRegressionRange)
    historical_metadata = [{'chrome_version': '51.0.1233.0', 'cpm': 0},
                           {'chrome_version': '51.0.1233.1', 'cpm': 0},
                           {'chrome_version': '51.0.1233.2', 'cpm': 0.89}]

    regression_range = findit_for_client.GetRegressionRange(
        CrashClient.FRACAS, {'historical_metadata': historical_metadata})
    self.assertEqual(regression_range, expected_regression_range)

    regression_range = findit_for_client.GetRegressionRange(
        'unsupported_client', {'historical_metadata': historical_metadata})
    self.assertEqual(regression_range, None)
