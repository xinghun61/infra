# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import logging

from common import appengine_util
from common import constants
from common import pubsub_util
from common import time_util
from common.http_client_appengine import HttpClientAppengine
from common.pipeline_wrapper import BasePipeline
from common.pipeline_wrapper import pipeline
from crash import findit_for_chromecrash
from crash import findit_for_clusterfuzz
from crash.type_enums import CrashClient
from lib.gitiles import gitiles_repository
from model import analysis_status
from model.crash.crash_config import CrashConfig


# TODO(http://crbug.com/659346): write complete coverage tests for this.
def FinditForClientID(client_id): # pragma: no cover
  """Construct a Findit object from a client id string specifying the class.

  We cannot pass Findit objects to the various methods in
  |crash.crash_pipeline|, because they are not JSON serializable. For now,
  we just serialize Findit objects as their |client_id|, and then use this
  function to reconstruct them. Alas, this means we will lose various
  other information stored in the Findit object (i.e., stuff that comes
  from CrashConfig); which could lead to some hard-to-diagnose coherency
  bugs, since the new Findit object will be based on the CrashConfig at
  the time it's constructed, which may be different than the CrashConfig
  at the time the previous Findit object was constructed. In the future
  we should fix all this to serialize Findit objects in a more robust way.
  """
  assert isinstance(client_id, (str, unicode)), (
      'FinditForClientID: expected string or unicode, but got %s'
      % client_id.__class__.__name__)
  # TODO(wrengr): it'd be nice to replace this with a single lookup in
  # a dict; but that's buggy for some unknown reason.
  if client_id == CrashClient.FRACAS:
    cls = findit_for_chromecrash.FinditForFracas
  elif client_id == CrashClient.CRACAS:
    cls = findit_for_chromecrash.FinditForCracas
  elif client_id == CrashClient.CLUSTERFUZZ:
    cls = findit_for_clusterfuzz.FinditForClusterfuzz
  else:
    raise ValueError('FinditForClientID: '
        'unknown or unsupported client %s' % client_id)

  return cls(
      gitiles_repository.GitilesRepository(http_client=HttpClientAppengine()),
      CrashWrapperPipeline)


# Some notes about the classes below, for people who are not
# familiar with AppEngine. The thing that really kicks everything off
# is |CrashWrapperPipeline.run|. However, an important thing to bear in
# mind is that whatever arguments are passed to that method will also
# be passed to the |run| method on whatever objects it yields. Thus,
# all the |run| methods across these different classes must have the same
# type. In practice, we end up passing all the arguments to the
# constructors, because we need to have the fields around for logging
# (e.g., in |finalized|); thus, there's nothing that needs to be passed
# to |run|. Another thing to bear in mind is that whatever objects
# |CrashWrapperPipeline.run| yields must be JSON-serializable. The base
# class handles most of that for us, so the force of this constraint is
# that all the arguments to the constructors for those classes must be
# JSON-serializable. Thus, we cannot actually pass a Findit object to
# the constructor, but rather must pass only the |client_id| (or whatever
# JSON dict) and then reconstruct the Findit object from that. Moreover,
# the |run| method and the |finalized| method will be run in different
# processes, so we will actually end up reconstructing the Findit object
# twice. Thus, we shouldn't store anything in the pipeline objects outside
# of what their constructors store.

class CrashBasePipeline(BasePipeline):
  def __init__(self, client_id, crash_identifiers):
    super(CrashBasePipeline, self).__init__(client_id, crash_identifiers)
    self._crash_identifiers = crash_identifiers
    self._findit = FinditForClientID(client_id)

  @property
  def client_id(self): # pragma: no cover
    return self._findit.client_id

  def run(self, *args, **kwargs):
    raise NotImplementedError()


class CrashAnalysisPipeline(CrashBasePipeline):
  def finalized(self): # pragma: no cover
    if self.was_aborted:
      self._PutAbortedError()

  # N.B., this method must be factored out for unittest reasons; since
  # |finalized| takes no arguments (by AppEngine's spec) and |was_aborted|
  # can't be altered directly.
  def _PutAbortedError(self):
    """Update the ndb.Model to indicate that this pipeline was aborted."""
    logging.error('Aborted analysis for %s', repr(self._crash_identifiers))
    analysis = self._findit.GetAnalysis(self._crash_identifiers)
    analysis.status = analysis_status.ERROR
    analysis.put()

  # TODO(http://crbug.com/659346): we misplaced the coverage test; find it!
  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self):
    # TODO(wrengr): shouldn't this method somehow call _NeedsNewAnalysis
    # to guard against race conditions?
    analysis = self._findit.GetAnalysis(self._crash_identifiers)

    # Update the model's status to say we're in the process of doing analysis.
    analysis.pipeline_status_path = self.pipeline_status_path()
    analysis.status = analysis_status.RUNNING
    analysis.started_time = time_util.GetUTCNow()
    analysis.findit_version = appengine_util.GetCurrentVersion()
    analysis.put()

    # Actually do the analysis.
    result, tags = self._findit.FindCulprit(analysis).ToDicts()

    # Update model's status to say we're done, and save the results.
    analysis.completed_time = time_util.GetUTCNow()
    analysis.result = result
    for tag_name, tag_value in tags.iteritems():
      # TODO(http://crbug.com/602702): make it possible to add arbitrary tags.
      if hasattr(analysis, tag_name):
        setattr(analysis, tag_name, tag_value)
    analysis.status = analysis_status.COMPLETED
    analysis.put()


class PublishResultPipeline(CrashBasePipeline):
  # TODO(http://crbug.com/659346): we misplaced the coverage test; find it!
  def finalized(self):
    if self.was_aborted:  # pragma: no cover.
      logging.error('Failed to publish %s analysis result for %s',
                    repr(self._crash_identifiers), self.client_id)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self):
    analysis = self._findit.GetAnalysis(self._crash_identifiers)
    result = analysis.ToPublishableResult(self._crash_identifiers)
    messages_data = [json.dumps(result, sort_keys=True)]

    # TODO(http://crbug.com/659354): remove Findit's dependency on CrashConfig.
    client_config = self._findit.config
    # TODO(katesonia): Clean string uses in config.
    topic = client_config['analysis_result_pubsub_topic']
    pubsub_util.PublishMessagesToTopic(messages_data, topic)
    logging.info('Published %s analysis result for %s', self.client_id,
                 repr(self._crash_identifiers))


class CrashWrapperPipeline(BasePipeline):
  """Fire off pipelines to (1) do the analysis and (2) publish results.

  The reason we have analysis and publishing as separate pipelines is
  because each of them can fail for independent reasons. E.g., if we
  successfully finish the analysis, but then the publishing fails due to
  network errors, we don't want to have to redo the analysis in order
  to redo the publishing. We could try to cache the fact that analysis
  succeeded in the pipeline object itself, but we'd have to be careful
  because the |run| and |finalized| methods are executed in different
  processes.
  """
  def __init__(self, client_id, crash_identifiers):
    super(CrashWrapperPipeline, self).__init__(client_id, crash_identifiers)
    self._crash_identifiers = crash_identifiers
    self._client_id = client_id

  # TODO(http://crbug.com/659346): write coverage tests.
  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self): # pragma: no cover
    run_analysis = yield CrashAnalysisPipeline(
        self._client_id, self._crash_identifiers)
    with pipeline.After(run_analysis):
      yield PublishResultPipeline(self._client_id, self._crash_identifiers)
