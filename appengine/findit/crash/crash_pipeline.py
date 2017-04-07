# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import logging

from crash import monitoring

from crash import findit_for_chromecrash
from crash import findit_for_clusterfuzz
from crash.type_enums import CrashClient
from gae_libs import appengine_util
from gae_libs import pubsub_util
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from libs import time_util
from model.crash.crash_config import CrashConfig


# TODO(http://crbug.com/659346): write complete coverage tests for this.
def FinditForClientID(client_id, get_repository, config): # pragma: no cover
  """Construct a Findit object from a client id string specifying the class.

  We cannot pass Findit objects to the various methods in
  ``crash.crash_pipeline``, because they are not JSON serializable. For
  now, we just serialize Findit objects as their ``client_id``, and then
  use this function to reconstruct them. Alas, this means we will lose
  various other information stored in the Findit object (i.e., stuff that
  comes from CrashConfig); which could lead to some hard-to-diagnose
  coherency bugs, since the new Findit object will be based on the
  CrashConfig at the time it's constructed, which may be different
  than the CrashConfig at the time the previous Findit object was
  constructed. In the future we should fix all this to serialize Findit
  objects in a more robust way.
  """
  assert isinstance(client_id, (str, unicode)), (
      'FinditForClientID: expected string or unicode, but got %s'
      % client_id.__class__.__name__)
  # TODO(wrengr): it'd be nice to replace this with a single lookup in
  # a dict; but that's buggy for some unknown reason.
  if client_id == CrashClient.FRACAS:
    cls = findit_for_chromecrash.FinditForFracas
  elif client_id == CrashClient.CRACAS: # pragma: no cover
    cls = findit_for_chromecrash.FinditForCracas
  elif client_id == CrashClient.CLUSTERFUZZ: # pragma: no cover
    cls = findit_for_clusterfuzz.FinditForClusterfuzz
  else: # pragma: no cover
    raise ValueError('FinditForClientID: '
        'unknown or unsupported client %s' % client_id)

  return cls(get_repository, config)


# Some notes about the classes below, for people who are not familiar
# with AppEngine pipelines:
#
# The pipeline library is designed in a strange way which requires that
# all the ``__init__`` and ``run`` methods in this file take the exact
# same arguments. This arises from the interaction between a few
# different constraints. First, for any given pipeline, its ``__init__``
# and ``run`` must take the same arguments. Second, all the objects that
# ``CrashWrapperPipeline.run`` yields must take the same arguments as that
# ``run`` method itself. For more about all this, see:
# https://github.com/GoogleCloudPlatform/appengine-pipelines/wiki/Python
# For our use case, we pass all the important data to ``__init__``,
# since we need it to be available in ``finalized``; thus we ignore the
# arguments passed to ``run`` (which will be the same values that were
# passed to ``__init__``).
#
# In addition, whatever objects ``CrashWrapperPipeline.run`` yields must
# be JSON-serializable. The pipeline class handles most of the details,
# so the force of this constraint is that whatever arguments we pass
# to their ``__init__`` must themselves be JSON-serializable. Alas,
# in Python, JSON-serializability isn't a property of classes themselves,
# but rather a property of the JSON-encoder object used to do the
# serialization. Thus, we cannot pass a ``Findit`` object directly to
# any of the methods here, but rather must instead pass the ``client_id``
# (or whatever JSON dict), and then reconstruct the ``Findit`` object
# from that data.
#
# Moreover, the ``run`` and ``finalized`` methods are executed in separate
# processes, so we'll actually end up reconstructing the ``Findit`` object
# twice. This also means ``run`` can't store anything in the pipeline
# object and expect it to still be available in the ``finalized`` method.

class CrashBasePipeline(BasePipeline):
  def __init__(self, client_id, crash_identifiers):
    super(CrashBasePipeline, self).__init__(client_id, crash_identifiers)
    self._crash_identifiers = crash_identifiers
    self._findit = FinditForClientID(
        client_id,
        CachedGitilesRepository.Factory(HttpClientAppengine()),
        CrashConfig.Get())

  @property
  def client_id(self): # pragma: no cover
    return self._findit.client_id

  def run(self, *args, **kwargs):
    raise NotImplementedError()


class CrashAnalysisPipeline(CrashBasePipeline):
  def finalized(self):
    if self.was_aborted: # pragma: no cover
      self._PutAbortedError()

  # N.B., this method must be factored out for unittest reasons; since
  # ``finalized`` takes no arguments (by AppEngine's spec) and
  # ``was_aborted`` can't be altered directly.
  def _PutAbortedError(self):
    """Update the ndb.Model to indicate that this pipeline was aborted."""
    logging.error('Aborted analysis for %s', repr(self._crash_identifiers))
    analysis = self._findit.GetAnalysis(self._crash_identifiers)
    analysis.status = analysis_status.ERROR
    analysis.put()

  def run(self, *_args, **_kwargs):
    """Call predator to do the analysis of the given crash.

    N.B., due to the structure of AppEngine pipelines, this method must
    accept the same arguments as are passed to ``__init__``; however,
    because they were already passed to ``__init__`` there's no use in
    recieving them here. Thus, we discard all the arguments to this method
    (except for ``self``, naturally).
    """
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
    culprit = self._findit.FindCulprit(analysis.ToCrashReport())
    if culprit is not None:
      result, tags = culprit.ToDicts()
    else:
      result = {'found': False}
      tags = {
          'found_suspects': False,
          'found_project': False,
          'found_components': False,
          'has_regression_range': False,
          'solution': None,
      }

    # Update model's status to say we're done, and save the results.
    analysis.completed_time = time_util.GetUTCNow()
    analysis.result = result
    for tag_name, tag_value in tags.iteritems():
      # TODO(http://crbug.com/602702): make it possible to add arbitrary tags.
      # TODO(http://crbug.com/659346): we misplaced the coverage test; find it!
      if hasattr(analysis, tag_name): # pragma: no cover
        setattr(analysis, tag_name, tag_value)

      if hasattr(monitoring, tag_name):
        metric = getattr(monitoring, tag_name)
        metric.increment({tag_name: tag_value,
                          'client_id': self.client_id})

    analysis.status = analysis_status.COMPLETED
    analysis.put()


class PublishResultPipeline(CrashBasePipeline):
  def finalized(self):
    if self.was_aborted: # pragma: no cover.
      logging.error('Failed to publish %s analysis result for %s',
                    repr(self._crash_identifiers), self.client_id)

  # TODO(http://crbug.com/659346): we misplaced the coverage test; find it!
  def run(self, *_args, **_kwargs): # pragma: no cover
    """Publish the results of our analysis back into the ndb.Model.

    N.B., due to the structure of AppEngine pipelines, this method must
    accept the same arguments as are passed to ``__init__``; however,
    because they were already passed to ``__init__`` there's no use in
    recieving them here. Thus, we discard all the arguments to this method
    (except for ``self``, naturally).
    """
    analysis = self._findit.GetAnalysis(self._crash_identifiers)
    if not analysis or not analysis.result or analysis.failed:
      logging.info('Can\'t publish result to %s because analysis failed:\n%s',
                   self.client_id, repr(self._crash_identifiers))
      return

    result = self._findit.GetPublishableResult(self._crash_identifiers,
                                               analysis)
    messages_data = [json.dumps(result, sort_keys=True)]

    # TODO(http://crbug.com/659354): remove Findit's dependency on CrashConfig.
    client_config = self._findit.client_config
    # TODO(katesonia): Clean string uses in config.
    topic = client_config['analysis_result_pubsub_topic']
    pubsub_util.PublishMessagesToTopic(messages_data, topic)
    logging.info('Published %s analysis result for %s', self.client_id,
                 repr(self._crash_identifiers))


# TODO(http://crbug.com/659346): we misplaced the coverage test; find it!
class CrashWrapperPipeline(BasePipeline): # pragma: no cover
  """Fire off pipelines to (1) do the analysis and (2) publish results.

  The reason we have analysis and publishing as separate pipelines is
  because each of them can fail for independent reasons. E.g., if we
  successfully finish the analysis, but then the publishing fails due to
  network errors, we don't want to have to redo the analysis in order
  to redo the publishing. We could try to cache the fact that analysis
  succeeded in the pipeline object itself, but we'd have to be careful
  because the ``run`` and ``finalized`` methods are executed in different
  processes.
  """
  def __init__(self, client_id, crash_identifiers):
    super(CrashWrapperPipeline, self).__init__(client_id, crash_identifiers)
    self._crash_identifiers = crash_identifiers
    self._client_id = client_id

  def run(self, *_args, **_kwargs):
    """Fire off pipelines to run the analysis and publish its results.

    N.B., due to the structure of AppEngine pipelines, this method must
    accept the same arguments as are passed to ``__init__``; however,
    because they were already passed to ``__init__`` there's no use in
    recieving them here. Thus, we discard all the arguments to this method
    (except for ``self``, naturally).
    """
    run_analysis = yield CrashAnalysisPipeline(
        self._client_id, self._crash_identifiers)
    with pipeline.After(run_analysis):
      yield PublishResultPipeline(self._client_id, self._crash_identifiers)
