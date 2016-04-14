# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

from common import constants
from common.pipeline_wrapper import pipeline_handlers
from crash import fracas_crash_pipeline
from crash.test.crash_testcase import CrashTestCase
from model import analysis_status
from model import result_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis
from waterfall.test import wf_testcase


class FracasCrashPipelineTest(CrashTestCase):
  app_module = pipeline_handlers._APP

  def testNoAnalysisIfLastOneIsNotFailed(self):
    channel = 'canary'
    platform = 'win'
    signature = 'signature'
    for status in (analysis_status.PENDING, analysis_status.RUNNING,
                   analysis_status.COMPLETED, analysis_status.SKIPPED):
      analysis = FracasCrashAnalysis.Create(channel, platform, signature)
      analysis.status = status
      analysis.put()
      self.assertFalse(fracas_crash_pipeline._NeedsNewAnalysis(
          channel, platform, signature, None, None, None))

  def testAnalysisNeededIfLastOneFailed(self):
    channel = 'canary'
    platform = 'win'
    signature = 'signature'
    analysis = FracasCrashAnalysis.Create(channel, platform, signature)
    analysis.status = analysis_status.ERROR
    analysis.put()
    self.assertTrue(fracas_crash_pipeline._NeedsNewAnalysis(
        channel, platform, signature, None, None, None))

  def testAnalysisNeededIfNoAnalysisYet(self):
    channel = 'canary'
    platform = 'win'
    signature = 'signature'
    self.assertTrue(fracas_crash_pipeline._NeedsNewAnalysis(
        channel, platform, signature, None, None, None))

  def testUnsupportedChannelOrPlatformSkipped(self):
    self.assertFalse(
        fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
            'unsupported_channel', 'win', None, None, None, None))
    self.assertFalse(
        fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
            'supported_channel', 'unsupported_platform',
            None, None, None, None))

  def testNoAnalysisNeeded(self):
    channel = 'supported_channel'
    platform = 'supported_platform'
    signature = 'signature'
    analysis = FracasCrashAnalysis.Create(channel, platform, signature)
    analysis.status = analysis_status.COMPLETED
    analysis.put()

    self.assertFalse(
        fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
            channel, platform, signature, None, None, None))

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

    channel = 'supported_channel'
    platform = 'supported_platform'
    signature = 'signature/here'
    stack_trace = 'frame1\nframe2\nframe3'
    chrome_version = '50.2500.0.0'
    versions_to_cpm = {'50.2500.0.0': 1.0}

    self.assertTrue(
        fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
            channel, platform, signature, stack_trace,
            chrome_version, versions_to_cpm))

    self.execute_queued_tasks()

    self.assertEqual(1, len(pubsub_publish_requests))
    expected_messages_data = [json.dumps({
          'channel': channel,
          'platform': platform,
          'signature': signature,
          'result': analysis_result,
        }, sort_keys=True)]
    self.assertEqual(expected_messages_data, pubsub_publish_requests[0][0])

    self.assertEqual(1, len(analyzed_crashes))
    self.assertEqual(
        (channel, platform, signature, stack_trace,
         chrome_version, versions_to_cpm),
        analyzed_crashes[0])

    analysis = FracasCrashAnalysis.Get(channel, platform, signature)
    self.assertEqual(analysis_result, analysis.result)
    self.assertTrue(analysis.has_regression_range)
    self.assertTrue(analysis.found_suspects)
    self.assertEqual('core', analysis.solution)

  def testAnalysisAborted(self):
    channel = 'canary'
    platform = 'win'
    signature = 'signature'
    analysis = FracasCrashAnalysis.Create(channel, platform, signature)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    pipeline = fracas_crash_pipeline.FracasAnalysisPipeline(
        channel, platform, signature)
    pipeline._SetErrorIfAborted(True)
    analysis = FracasCrashAnalysis.Get(channel, platform, signature)
    self.assertEqual(analysis_status.ERROR, analysis.status)
