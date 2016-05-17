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


# TODO(katesonia): Move these to config page.
_SIGNATURE_BLACKLIST_MARKERS = ['[Android Java Exception]']
_PLATFORM_RENAME = {'linux': 'unix'}


class FracasBasePipeline(BasePipeline):
  def __init__(self, crash_identifiers):
    super(FracasBasePipeline, self).__init__(crash_identifiers)
    self.crash_identifiers = crash_identifiers

  def run(self, *args, **kwargs):
    raise NotImplementedError()


class FracasAnalysisPipeline(FracasBasePipeline):
  def _SetErrorIfAborted(self, aborted):
    if not aborted:
      return

    logging.error('Aborted analysis for %s', repr(self.crash_identifiers))
    analysis = FracasCrashAnalysis.Get(self.crash_identifiers)
    analysis.status = analysis_status.ERROR
    analysis.put()

  def finalized(self):
    self._SetErrorIfAborted(self.was_aborted)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, crash_identifiers):
    analysis = FracasCrashAnalysis.Get(crash_identifiers)

    # Update analysis status.
    analysis.pipeline_status_path = self.pipeline_status_path()
    analysis.status = analysis_status.RUNNING
    analysis.started_time = datetime.datetime.utcnow()
    analysis.findit_version = appengine_util.GetCurrentVersion()
    analysis.put()

    # Run the analysis.
    result, tags = fracas.FindCulpritForChromeCrash(
        analysis.signature, analysis.platform, analysis.stack_trace,
        analysis.crashed_version, analysis.historic_metadata)

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
      logging.error('Failed to publish analysis result for %s',
                    repr(self.crash_identifiers))

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, crash_identifiers):
    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    result = {
        'crash_identifiers': crash_identifiers,
        'client_id': analysis.client_id,
        'result': analysis.result,
    }
    messages_data = [json.dumps(result, sort_keys=True)]

    crash_config = CrashConfig.Get()
    topic = crash_config.fracas['analysis_result_pubsub_topic']
    pubsub_util.PublishMessagesToTopic(messages_data, topic)
    logging.info('Published analysis result for %s', repr(crash_identifiers))


class FracasCrashWrapperPipeline(BasePipeline):
  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, crash_identifiers):
    run_analysis = yield FracasAnalysisPipeline(crash_identifiers)
    with pipeline.After(run_analysis):
      yield PublishResultPipeline(crash_identifiers)


@ndb.transactional
def _NeedsNewAnalysis(
    crash_identifiers, chrome_version, signature, client_id,
    platform, stack_trace, channel, historic_metadata):
  analysis = FracasCrashAnalysis.Get(crash_identifiers)
  if analysis and not analysis.failed:
    # A new analysis is not needed if last one didn't complete or succeeded.
    # TODO(http://crbug.com/600535): re-analyze if stack trace or regression
    # range changed.
    logging.info('The analysis of %s has already been done.',
                 repr(crash_identifiers))
    return False

  if not analysis:
    # A new analysis is needed if there is no analysis yet.
    analysis = FracasCrashAnalysis.Create(crash_identifiers)

  analysis.Reset()

  # Set common properties.
  analysis.crashed_version = chrome_version
  analysis.stack_trace = stack_trace
  analysis.signature = signature
  analysis.platform = platform
  analysis.client_id = client_id

  # Set customized properties.
  analysis.historic_metadata = historic_metadata
  analysis.channel = channel

  # Set analysis progress properties.
  analysis.status = analysis_status.PENDING
  analysis.requested_time = datetime.datetime.utcnow()

  analysis.put()

  return True


def ScheduleNewAnalysisForCrash(
    crash_identifiers, chrome_version, signature, client_id,
    platform, stack_trace, channel, historic_metadata,
    queue_name=constants.DEFAULT_QUEUE):
  """Schedules an analysis."""
  crash_config = CrashConfig.Get()
  if platform not in crash_config.fracas.get(
      'supported_platform_list_by_channel', {}).get(channel, []):
    # Bail out if either the channel or platform is not supported yet.
    logging.info('Ananlysis of channel %s, platform %s is not supported. '
                 'No analysis is scheduled for %s',
                 channel, platform, repr(crash_identifiers))
    return False

  for blacklist_marker in _SIGNATURE_BLACKLIST_MARKERS:
    if blacklist_marker in signature:
      logging.info('%s signature is not supported. '
                   'No analysis is scheduled for %s', blacklist_marker,
                   repr(crash_identifiers))
      return False

  if platform in _PLATFORM_RENAME:
    platform = _PLATFORM_RENAME[platform]

  if _NeedsNewAnalysis(crash_identifiers, chrome_version, signature, client_id,
                       platform, stack_trace, channel, historic_metadata):
    analysis_pipeline = FracasCrashWrapperPipeline(crash_identifiers)
    analysis_pipeline.target = appengine_util.GetTargetNameForModule(
        constants.CRASH_BACKEND_FRACAS)
    analysis_pipeline.start(queue_name=queue_name)
    logging.info('New analysis is scheduled for %s', repr(crash_identifiers))
    return True

  return False
