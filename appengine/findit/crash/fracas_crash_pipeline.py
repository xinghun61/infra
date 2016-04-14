# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import datetime
import json
import logging

from google.appengine.ext import ndb

from common import appengine_util
from common import constants
from common import pubsub_util
from common.pipeline_wrapper import BasePipeline
from common.pipeline_wrapper import pipeline
from crash import fracas
from model import analysis_status
from model.crash.crash_config import CrashConfig
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class FracasBasePipeline(BasePipeline):
  def __init__(self, channel, platform, signature):
    super(FracasBasePipeline, self).__init__(
        channel, platform, signature)
    self.channel = channel
    self.platform = platform
    self.signature = signature

  def run(self, *args, **kwargs):
    raise NotImplementedError()


class FracasAnalysisPipeline(FracasBasePipeline):
  def _SetErrorIfAborted(self, aborted):
    if not aborted:
      return

    logging.error('Aborted analysis for %s, %s, %s',
                  self.channel, self.platform, self.signature)
    analysis = FracasCrashAnalysis.Get(
        self.channel, self.platform, self.signature)
    analysis.status = analysis_status.ERROR
    analysis.put()

  def finalized(self):
    self._SetErrorIfAborted(self.was_aborted)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, channel, platform, signature):
    analysis = FracasCrashAnalysis.Get(channel, platform, signature)

    # Update analysis status.
    analysis.pipeline_status_path = self.pipeline_status_path()
    analysis.status = analysis_status.RUNNING
    analysis.started_time = datetime.datetime.utcnow()
    analysis.findit_version = appengine_util.GetCurrentVersion()
    analysis.put()

    # Run the analysis.
    result, tags = fracas.FindCulpritForChromeCrash(
        channel, platform, signature, analysis.stack_trace,
        analysis.crashed_version, analysis.versions_to_cpm)

    # Update analysis status and save the analysis result.
    analysis.completed_time = datetime.datetime.utcnow()
    analysis.result = result
    for tag_name, tag_value in tags.iteritems():
      # TODO(http://crbug.com/602702): make it possible to add arbitrary tags.
      if hasattr(analysis, tag_name):
        setattr(analysis, tag_name, tag_value)
    analysis.status = analysis_status.COMPLETED
    analysis.put()


class PublishResultPipeline(FracasBasePipeline):
  def finalized(self):
    if self.was_aborted:  # pragma: no cover.
      logging.error('Failed to publish analysis result for %s, %s, %s',
                    self.channel, self.platform, self.signature)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, channel, platform, signature):
    analysis = FracasCrashAnalysis.Get(channel, platform, signature)
    result = {
        'channel': channel,
        'platform': platform,
        'signature': signature,
        'result': analysis.result,
    }
    messages_data = [json.dumps(result, sort_keys=True)]

    crash_config = CrashConfig.Get()
    topic = crash_config.fracas['analysis_result_pubsub_topic']
    pubsub_util.PublishMessagesToTopic(messages_data, topic)
    logging.info('Published analysis result for %s, %s, %s',
                 channel, platform, signature)


class FracasCrashWrapperPipeline(BasePipeline):
  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, channel, platform, signature):
    run_analysis = yield FracasAnalysisPipeline(channel, platform, signature)
    with pipeline.After(run_analysis):
      yield PublishResultPipeline(channel, platform, signature)


@ndb.transactional
def _NeedsNewAnalysis(
    channel, platform, signature, stack_trace, chrome_version, versions_to_cpm):
  analysis = FracasCrashAnalysis.Get(channel, platform, signature)
  if analysis and not analysis.failed:
    # A new analysis is not needed if last one didn't complete or succeeded.
    # TODO(http://crbug.com/600535): re-analyze if stack trace or regression
    # range changed.
    return False

  if not analysis:
    # A new analysis is needed if there is no analysis yet.
    analysis = FracasCrashAnalysis.Create(channel, platform, signature)

  analysis.Reset()
  analysis.crashed_version = chrome_version
  analysis.stack_trace = stack_trace
  analysis.versions_to_cpm = versions_to_cpm
  analysis.status = analysis_status.PENDING
  analysis.requested_time = datetime.datetime.utcnow()
  analysis.put()
  return True


def ScheduleNewAnalysisForCrash(
    channel, platform, signature, stack_trace, chrome_version, versions_to_cpm,
    queue_name=constants.DEFAULT_QUEUE):
  """Schedules an analysis."""
  crash_config = CrashConfig.Get()
  if platform not in crash_config.fracas.get(
      'supported_platform_list_by_channel', {}).get(channel, []):
    # Bail out if either the channel or platform is not supported yet.
    return False

  if _NeedsNewAnalysis(channel, platform, signature, stack_trace,
                       chrome_version, versions_to_cpm):
    analysis_pipeline = FracasCrashWrapperPipeline(channel, platform, signature)
    analysis_pipeline.target = appengine_util.GetTargetNameForModule(
        constants.CRASH_BACKEND_FRACAS)
    analysis_pipeline.start(queue_name=queue_name)
    logging.info('New analysis is scheduled for %s, %s, %s',
                 channel, platform, signature)
    return True

  return False
