# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import logging

from google.appengine.api import app_identity
from google.appengine.ext import ndb

from common import appengine_util
from common import constants
from common import pubsub_util
from common import time_util
from common.pipeline_wrapper import BasePipeline
from common.pipeline_wrapper import pipeline
from crash import findit_for_client
from model import analysis_status
from model.crash.crash_config import CrashConfig


class CrashBasePipeline(BasePipeline):
  def __init__(self, crash_identifiers, client_id):
    super(CrashBasePipeline, self).__init__(crash_identifiers, client_id)
    self.crash_identifiers = crash_identifiers
    self.client_id = client_id

  def run(self, *args, **kwargs):
    raise NotImplementedError()


class CrashAnalysisPipeline(CrashBasePipeline):
  def _SetErrorIfAborted(self, aborted):
    if not aborted:
      return

    logging.error('Aborted analysis for %s', repr(self.crash_identifiers))
    analysis = findit_for_client.GetAnalysisForClient(self.crash_identifiers,
                                                      self.client_id)
    analysis.status = analysis_status.ERROR
    analysis.put()

  def finalized(self):
    self._SetErrorIfAborted(self.was_aborted)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, crash_identifiers, client_id):
    analysis = findit_for_client.GetAnalysisForClient(crash_identifiers,
                                                      client_id)

    # Update analysis status.
    analysis.pipeline_status_path = self.pipeline_status_path()
    analysis.status = analysis_status.RUNNING
    analysis.started_time = time_util.GetUTCNow()
    analysis.findit_version = appengine_util.GetCurrentVersion()
    analysis.put()

    # Run the analysis.
    result, tags = findit_for_client.FindCulprit(analysis)

    # Update analysis status and save the analysis result.
    analysis.completed_time = time_util.GetUTCNow()
    analysis.result = result
    for tag_name, tag_value in tags.iteritems():
      # TODO(http://crbug.com/602702): make it possible to add arbitrary tags.
      if hasattr(analysis, tag_name):
        setattr(analysis, tag_name, tag_value)
    analysis.status = analysis_status.COMPLETED
    analysis.put()


class PublishResultPipeline(CrashBasePipeline):
  def finalized(self):
    if self.was_aborted:  # pragma: no cover.
      logging.error('Failed to publish %s analysis result for %s',
                    repr(self.crash_identifiers), self.client_id)


  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, crash_identifiers, client_id):
    analysis = findit_for_client.GetAnalysisForClient(crash_identifiers,
                                                      client_id)
    result = findit_for_client.GetPublishResultFromAnalysis(analysis,
                                                            crash_identifiers,
                                                            client_id)
    messages_data = [json.dumps(result, sort_keys=True)]

    client_config = CrashConfig.Get().GetClientConfig(client_id)
    # TODO(katesonia): Clean string uses in config.
    topic = client_config['analysis_result_pubsub_topic']
    pubsub_util.PublishMessagesToTopic(messages_data, topic)
    logging.info('Published %s analysis result for %s', client_id,
                 repr(crash_identifiers))


class CrashWrapperPipeline(BasePipeline):
  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, crash_identifiers, client_id):
    run_analysis = yield CrashAnalysisPipeline(crash_identifiers, client_id)
    with pipeline.After(run_analysis):
      yield PublishResultPipeline(crash_identifiers, client_id)


@ndb.transactional
def _NeedsNewAnalysis(
    crash_identifiers, chrome_version, signature, client_id,
    platform, stack_trace, customized_data):
  analysis = findit_for_client.GetAnalysisForClient(crash_identifiers,
                                                    client_id)
  if analysis and not analysis.failed:
    # A new analysis is not needed if last one didn't complete or succeeded.
    # TODO(http://crbug.com/600535): re-analyze if stack trace or regression
    # range changed.
    logging.info('The analysis of %s has already been done.',
                 repr(crash_identifiers))
    return False

  # Create analysis for findit to run if this is not a rerun.
  if not analysis:
    analysis = findit_for_client.CreateAnalysisForClient(crash_identifiers,
                                                         client_id)

  findit_for_client.ResetAnalysis(analysis, chrome_version, signature,
                                  client_id,  platform, stack_trace,
                                  customized_data)
  return True


def ScheduleNewAnalysisForCrash(
    crash_identifiers, chrome_version, signature, client_id,
    platform, stack_trace, customized_data,
    queue_name=constants.DEFAULT_QUEUE):
  """Schedules an analysis."""
  # Check policy and tune arguments if needed.
  pass_policy, updated_analysis_args = findit_for_client.CheckPolicyForClient(
      crash_identifiers, chrome_version, signature,
      client_id, platform, stack_trace,
      customized_data)

  if not pass_policy:
    return False

  if _NeedsNewAnalysis(*updated_analysis_args):
    analysis_pipeline = CrashWrapperPipeline(crash_identifiers, client_id)
    # Attribute defined outside __init__ - pylint: disable=W0201
    analysis_pipeline.target = appengine_util.GetTargetNameForModule(
        constants.CRASH_BACKEND[client_id])
    analysis_pipeline.start(queue_name=queue_name)
    logging.info('New %s analysis is scheduled for %s', client_id,
                 repr(crash_identifiers))
    return True

  return False
