# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from common.pipeline_wrapper import pipeline_handlers
from crash import fracas_crash_pipeline
from crash.test.crash_testcase import CrashTestCase
from model import analysis_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class FracasCrashPipelineTest(CrashTestCase):
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
      self.assertFalse(fracas_crash_pipeline._NeedsNewAnalysis(
          crash_identifiers, chrome_version, signature, 'fracas',
          platform, None, None, None))

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
    self.assertTrue(fracas_crash_pipeline._NeedsNewAnalysis(
          crash_identifiers, chrome_version, signature, 'fracas',
          platform, None, None, None))

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
    self.assertTrue(fracas_crash_pipeline._NeedsNewAnalysis(
          crash_identifiers, chrome_version, signature, 'fracas',
          platform, None, None, None))

  def testUnsupportedChannelOrPlatformSkipped(self):
    self.assertFalse(
        fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
            {}, None, None, 'fracas', 'win',
            None, 'unsupported_channel',  None))
    self.assertFalse(
        fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
            {}, None, None, 'fracas', 'unsupported_platform',
            None, 'unsupported_channel',  None))

  def testBlackListSignatureSipped(self):
    self.assertFalse(
        fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
            {}, None, '[Android Java Exception] signature', 'fracas', 'win',
            None, 'canary',  None))

  def testPlatformRename(self):
    def _MockNeedsNewAnalysis(*args):
      self.assertEqual(args,
                       ({}, None, 'signature', 'fracas', 'unix', None,
                        'canary', None))
      return False

    self.mock(fracas_crash_pipeline, '_NeedsNewAnalysis', _MockNeedsNewAnalysis)

    fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
        {}, None, 'signature', 'fracas', 'linux',
        None, 'canary',  None)

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
        fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
            crash_identifiers, chrome_version, signature, 'fracas',
            platform, None, channel, None))

  def testRunningAnalysis(self):
    pubsub_publish_requests = []
    def Mocked_PublishMessagesToTopic(messages_data, topic):
      pubsub_publish_requests.append((messages_data, topic))
    self.mock(fracas_crash_pipeline.pubsub_util, 'PublishMessagesToTopic',
              Mocked_PublishMessagesToTopic)

    analysis_result = {
        'found': True,
        'other_data': 'data',
    }
    analysis_tags = {
        'found_suspects': True,
        'has_regression_range': True,
        'solution': 'core',
        'unsupported_tag': '',
    }
    analyzed_crashes = []
    def Mocked_FindCulpritForChromeCrash(*args):
      analyzed_crashes.append(args)
      return analysis_result, analysis_tags
    self.mock(fracas_crash_pipeline.fracas, 'FindCulpritForChromeCrash',
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
    historic_metadata = {'50.2500.0.0': 1.0}

    self.assertTrue(
        fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
            crash_identifiers, chrome_version, signature, 'fracas',
            platform, stack_trace, channel, historic_metadata))

    self.execute_queued_tasks()

    self.assertEqual(1, len(pubsub_publish_requests))
    expected_messages_data = [json.dumps({
            'crash_identifiers': crash_identifiers,
            'client_id': 'fracas',
            'result': analysis_result,
        }, sort_keys=True)]
    self.assertEqual(expected_messages_data, pubsub_publish_requests[0][0])

    self.assertEqual(1, len(analyzed_crashes))
    self.assertEqual(
        (signature, platform, stack_trace, chrome_version, historic_metadata),
        analyzed_crashes[0])

    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_result, analysis.result)
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

    pipeline = fracas_crash_pipeline.FracasAnalysisPipeline(crash_identifiers)
    pipeline._SetErrorIfAborted(True)
    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_status.ERROR, analysis.status)
