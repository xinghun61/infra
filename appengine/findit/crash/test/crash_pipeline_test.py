# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import json

from google.appengine.api import app_identity

from common.pipeline_wrapper import pipeline_handlers
from crash import crash_pipeline
from crash import findit_for_chromecrash
from crash.test.crash_testcase import CrashTestCase
from model import analysis_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class CrashPipelineTest(CrashTestCase):
  app_module = pipeline_handlers._APP

  def testNoAnalysisIfLastOneIsNotFailed(self):
    chrome_version = '1'
    signature = 'signature'
    platform = 'win'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': 'canary',
      'platform': platform,
      'process_type': 'browser',
    }
    for status in (analysis_status.PENDING, analysis_status.RUNNING,
                   analysis_status.COMPLETED, analysis_status.SKIPPED):
      analysis = FracasCrashAnalysis.Create(crash_identifiers)
      analysis.status = status
      analysis.put()
      self.assertFalse(crash_pipeline._NeedsNewAnalysis(
          crash_identifiers, chrome_version, signature, 'fracas',
          platform, None, {'channel': 'canary'}))

  def testAnalysisNeededIfLastOneFailed(self):
    chrome_version = '1'
    signature = 'signature'
    platform = 'win'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': 'canary',
      'platform': platform,
      'process_type': 'browser',
    }
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.ERROR
    analysis.put()
    self.assertTrue(crash_pipeline._NeedsNewAnalysis(
          crash_identifiers, chrome_version, signature, 'fracas',
          platform, None, {'channel': 'canary'}))

  def testAnalysisNeededIfNoAnalysisYet(self):
    chrome_version = '1'
    signature = 'signature'
    platform = 'win'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': 'canary',
      'platform': platform,
      'process_type': 'browser',
    }
    self.assertTrue(crash_pipeline._NeedsNewAnalysis(
          crash_identifiers, chrome_version, signature, 'fracas',
          platform, None, {'channel': 'canary'}))

  def testUnsupportedChannelOrPlatformSkipped(self):
    self.assertFalse(
        crash_pipeline.ScheduleNewAnalysisForCrash(
            {}, None, None, 'fracas', 'win',
            None, {'channel': 'unsupported_channel',
                   'historical_metadata': None}))
    self.assertFalse(
        crash_pipeline.ScheduleNewAnalysisForCrash(
            {}, None, None, 'fracas', 'unsupported_platform',
            None, {'channel': 'unsupported_channel',
                   'historical_metadata': None}))

  def testBlackListSignatureSipped(self):
    self.assertFalse(
        crash_pipeline.ScheduleNewAnalysisForCrash(
            {}, None, 'Blacklist marker signature', 'fracas', 'win',
            None, {'channel': 'canary',
                   'historical_metadata': None}))

  def testPlatformRename(self):
    def _MockNeedsNewAnalysis(*args):
      self.assertEqual(args,
                       ({}, None, 'signature', 'fracas', 'unix', None,
                        {'channel': 'canary'}))
      return False

    self.mock(crash_pipeline, '_NeedsNewAnalysis', _MockNeedsNewAnalysis)

    crash_pipeline.ScheduleNewAnalysisForCrash(
        {}, None, 'signature', 'fracas', 'linux',
        None, {'channel': 'canary'})

  def testNoAnalysisNeeded(self):
    chrome_version = '1'
    signature = 'signature'
    platform = 'win'
    channel = 'canary'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': channel,
      'platform': platform,
      'process_type': 'browser',
    }
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.COMPLETED
    analysis.put()

    self.assertFalse(
        crash_pipeline.ScheduleNewAnalysisForCrash(
            crash_identifiers, chrome_version, signature, 'fracas',
            platform, None, {'channel': channel,
                             'historical_metadata': None}))

  def _TestRunningAnalysisForResult(self, analysis_result, analysis_tags):
    pubsub_publish_requests = []
    def Mocked_PublishMessagesToTopic(messages_data, topic):
      pubsub_publish_requests.append((messages_data, topic))
    self.mock(crash_pipeline.pubsub_util, 'PublishMessagesToTopic',
              Mocked_PublishMessagesToTopic)

    analyzed_crashes = []
    def Mocked_FindCulpritForChromeCrash(*args):
      analyzed_crashes.append(args)
      return analysis_result, analysis_tags
    self.mock(findit_for_chromecrash, 'FindCulpritForChromeCrash',
              Mocked_FindCulpritForChromeCrash)
    chrome_version = '1'
    signature = 'signature'
    platform = 'win'
    channel = 'canary'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': channel,
      'platform': platform,
      'process_type': 'browser',
    }
    stack_trace = 'frame1\nframe2\nframe3'
    chrome_version = '50.2500.0.0'
    historical_metadata = {'50.2500.0.0': 1.0}

    mock_host = 'https://host.com'
    self.mock(app_identity, 'get_default_version_hostname', lambda: mock_host)

    self.assertTrue(
        crash_pipeline.ScheduleNewAnalysisForCrash(
            crash_identifiers, chrome_version, signature, 'fracas',
            platform, stack_trace,
            {'channel': channel, 'historical_metadata': historical_metadata}))

    self.execute_queued_tasks()

    self.assertEqual(1, len(pubsub_publish_requests))

    processed_analysis_result = copy.deepcopy(analysis_result)
    processed_analysis_result['feedback_url'] = (
        mock_host + '/crash/fracas-result-feedback?'
        'key=agx0ZXN0YmVkLXRlc3RyQQsSE0ZyYWNhc0NyYXNoQW5hbHlzaXMiKGU2ZWIyNj'
        'A2OTBlYTAyMjVjNWNjYTM3ZTNjYTlmYWExOGVmYjVlM2UM')

    if 'suspected_cls' in processed_analysis_result:
      for cl in processed_analysis_result['suspected_cls']:
        cl['confidence'] = round(cl['confidence'], 2)
        cl.pop('reason', None)

    expected_messages_data = [json.dumps({
            'crash_identifiers': crash_identifiers,
            'client_id': 'fracas',
            'result': processed_analysis_result,
        }, sort_keys=True)]
    self.assertEqual(expected_messages_data, pubsub_publish_requests[0][0])

    self.assertEqual(1, len(analyzed_crashes))
    self.assertEqual(
        (signature, platform, stack_trace, chrome_version, historical_metadata),
        analyzed_crashes[0])

    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_result, analysis.result)
    return analysis


  def testRunningAnalysis(self):
    analysis_result = {
        'found': True,
        'suspected_cls': [],
        'other_data': 'data',
    }
    analysis_tags = {
        'found_suspects': True,
        'has_regression_range': True,
        'solution': 'core',
        'unsupported_tag': '',
    }

    analysis = self._TestRunningAnalysisForResult(
        analysis_result, analysis_tags)
    self.assertTrue(analysis.has_regression_range)
    self.assertTrue(analysis.found_suspects)
    self.assertEqual('core', analysis.solution)

  def testRunningAnalysisNoSuspectsFound(self):
    analysis_result = {
        'found': False
    }
    analysis_tags = {
        'found_suspects': False,
        'has_regression_range': False,
        'solution': 'core',
        'unsupported_tag': '',
    }

    analysis = self._TestRunningAnalysisForResult(
        analysis_result, analysis_tags)
    self.assertFalse(analysis.has_regression_range)
    self.assertFalse(analysis.found_suspects)
    self.assertEqual('core', analysis.solution)

  def testRunningAnalysisWithSuspectsCls(self):
    analysis_result = {
        'found': True,
        'suspected_cls': [
            {'confidence': 0.21434,
             'reason': ['reason1', 'reason2'],
             'other': 'data'}
        ],
        'other_data': 'data',
    }
    analysis_tags = {
        'found_suspects': True,
        'has_regression_range': True,
        'solution': 'core',
        'unsupported_tag': '',
    }

    analysis = self._TestRunningAnalysisForResult(
        analysis_result, analysis_tags)
    self.assertTrue(analysis.has_regression_range)
    self.assertTrue(analysis.found_suspects)
    self.assertEqual('core', analysis.solution)

  def testAnalysisAborted(self):
    chrome_version = '1'
    signature = 'signature'
    platform = 'win'
    crash_identifiers = {
      'chrome_version': chrome_version,
      'signature': signature,
      'channel': 'canary',
      'platform': platform,
      'process_type': 'browser',
    }
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    pipeline = crash_pipeline.CrashAnalysisPipeline(crash_identifiers, 'fracas')
    pipeline._SetErrorIfAborted(True)
    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_status.ERROR, analysis.status)
