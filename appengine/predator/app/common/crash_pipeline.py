# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import traceback

from google.appengine.ext import ndb

from analysis import log_util
from analysis.exceptions import PredatorError
from analysis.type_enums import CrashClient
from analysis.type_enums import LogLevel
from common import predator_for_chromecrash
from common import predator_for_clusterfuzz
from common import predator_for_uma_sampling_profiler
from common import monitoring
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis
from common.model.cracas_crash_analysis import CracasCrashAnalysis
from common.model.crash_analysis import CrashAnalysis
from common.model.crash_config import CrashConfig
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from common.model.log import Log
from gae_libs import appengine_util
from gae_libs import pubsub_util
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.iterator import Iterate
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from libs import time_util

CLIENT_ID_TO_CRASH_ANALYSIS = {
    CrashClient.FRACAS: FracasCrashAnalysis,
    CrashClient.CRACAS: CracasCrashAnalysis,
    CrashClient.CLUSTERFUZZ: ClusterfuzzAnalysis
}


# TODO(http://crbug.com/659346): write complete coverage tests for this.
def PredatorForClientID(client_id, get_repository, config,
                        log=None): # pragma: no cover
  """Construct a ``PredatorApp`` from a client id string specifying the class.

  We cannot pass PredatorApp objects to the various methods in
  ``crash.crash_pipeline``, because they are not JSON serializable. For now, we
  just serialize PredatorApp objects as their ``client_id``, and then use this
  function to reconstruct them. Alas, this means we will lose various other
  information stored in the PredatorApp object (i.e., stuff that comes from
  CrashConfig); which could lead to some hard-to-diagnose coherency bugs, since
  the new PredatorApp object will be based on the CrashConfig at the time it's
  constructed, which may be different than the CrashConfig at the time the
  previous PredatorApp object was constructed. In the future we should fix all
  this to serialize PredatorApp objects in a more robust way.
  """
  assert isinstance(client_id, (str, unicode)), (
      'PredatorForClientID: expected string or unicode, but got %s'
      % client_id.__class__.__name__)
  # TODO(wrengr): it'd be nice to replace this with a single lookup in
  # a dict; but that's buggy for some unknown reason.
  if client_id == CrashClient.FRACAS:
    cls = predator_for_chromecrash.PredatorForFracas
  elif client_id == CrashClient.CRACAS: # pragma: no cover
    cls = predator_for_chromecrash.PredatorForCracas
  elif client_id == CrashClient.CLUSTERFUZZ: # pragma: no cover
    cls = predator_for_clusterfuzz.PredatorForClusterfuzz
  elif client_id == CrashClient.UMA_SAMPLING_PROFILER:
    cls = predator_for_uma_sampling_profiler.PredatorForUMASamplingProfiler
  else: # pragma: no cover
    raise ValueError('PredatorForClientID: '
        'unknown or unsupported client %s' % client_id)

  return cls(get_repository, config, log=log)


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
# serialization. Thus, we cannot pass a ``PredatorApp`` object directly to
# any of the methods here, but rather must instead pass the ``client_id``
# (or whatever JSON dict), and then reconstruct the ``PredatorApp`` object
# from that data.
#
# Moreover, the ``run`` and ``finalized`` methods are executed in separate
# processes, so we'll actually end up reconstructing the ``PredatorApp`` object
# twice. This also means ``run`` can't store anything in the pipeline
# object and expect it to still be available in the ``finalized`` method.

class CrashBasePipeline(BasePipeline):
  def __init__(self, client_id, crash_identifiers):
    super(CrashBasePipeline, self).__init__(client_id, crash_identifiers)
    self._crash_identifiers = crash_identifiers
    self._predator = PredatorForClientID(
        client_id,
        CachedGitilesRepository.Factory(HttpClientAppengine()),
        CrashConfig.Get(), log=self.log)

  @property
  def client_id(self): # pragma: no cover
    return self._predator.client_id

  def run(self, *args, **kwargs):
    raise NotImplementedError()

  @property
  def log(self):
    return (Log.Get(self._crash_identifiers) or
            Log.Create(self._crash_identifiers))


class CrashAnalysisPipeline(CrashBasePipeline):
  """The pipeline to call Predator to do the analysis of a given crash."""

  def finalized(self):
    if self.was_aborted: # pragma: no cover
      self._PutAbortedError()
      raise PredatorError('Abort CrashAnalysisPipeline.')

  # N.B., this method must be factored out for unittest reasons; since
  # ``finalized`` takes no arguments (by AppEngine's spec) and
  # ``was_aborted`` can't be altered directly.
  def _PutAbortedError(self):
    """Update the ndb.Model to indicate that this pipeline was aborted."""
    log_util.LogError(self.log, 'PipelineAborted',
                      'Aborted analysis for %s' % repr(self._crash_identifiers))
    analysis = self._predator.GetAnalysis(self._crash_identifiers)
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
    logging.info('Start analysis of crash_pipeline. %s',
                 json.dumps(self._crash_identifiers))
    # TODO(wrengr): shouldn't this method somehow call _NeedsNewAnalysis
    # to guard against race conditions?
    analysis = self._predator.GetAnalysis(self._crash_identifiers)

    # Update the model's status to say we're in the process of doing analysis.
    analysis.pipeline_status_path = self.pipeline_status_path()
    analysis.status = analysis_status.RUNNING
    analysis.started_time = time_util.GetUTCNow()
    analysis.predator_version = appengine_util.GetCurrentVersion()
    analysis.put()

    # Actually do the analysis.
    success, culprit = self._predator.FindCulprit(analysis.ToCrashReport())
    result, tags = culprit.ToDicts()
    if success:
      analysis.status = analysis_status.COMPLETED
    else:
      analysis.status = analysis_status.ERROR

    analysis.completed_time = time_util.GetUTCNow()
    # Update model's status to say we're done, and save the results.
    analysis.result = result
    for tag_name, tag_value in tags.iteritems():
      # TODO(http://crbug.com/602702): make it possible to add arbitrary tags.
      # TODO(http://crbug.com/659346): we misplaced the coverage test;
      # find it!
      if hasattr(analysis, tag_name):  # pragma: no cover
        setattr(analysis, tag_name, tag_value)

      if hasattr(monitoring, tag_name):
        metric = getattr(monitoring, tag_name)
        metric.increment({tag_name: tag_value,
                          'client_id': self.client_id})
    analysis.put()

    logging.info('Found %s analysis result for %s: \n%s', self.client_id,
                 repr(self._crash_identifiers),
                 json.dumps(analysis.result, indent=2, sort_keys=True))


class PublishResultPipeline(CrashBasePipeline):
  def finalized(self):
    if self.was_aborted: # pragma: no cover.
      logging.error('Failed to publish %s analysis result for %s',
                    repr(self._crash_identifiers), self.client_id)
      raise PredatorError('Abort PublishResultPipeline.')

  # TODO(http://crbug.com/659346): we misplaced the coverage test; find it!
  def run(self, *_args, **_kwargs): # pragma: no cover
    """Publish the results of our analysis back into the ndb.Model.

    N.B., due to the structure of AppEngine pipelines, this method must
    accept the same arguments as are passed to ``__init__``; however,
    because they were already passed to ``__init__`` there's no use in
    recieving them here. Thus, we discard all the arguments to this method
    (except for ``self``, naturally).
    """
    self._predator.PublishResult(self._crash_identifiers)


class CrashWrapperPipeline(BasePipeline):
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


class RerunPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, client_id, crash_keys, publish_to_client=False):
    """Reruns analysis for a batch of crashes.

    Args:
      client_id (CrashClient): The client whose crash we should iterate.
      crash_keys (list): A list of urlsafe encodings of crash keys.
    """
    client = PredatorForClientID(
        client_id,
        CachedGitilesRepository.Factory(HttpClientAppengine()),
        CrashConfig.Get())

    updated = []
    for key in crash_keys:
      key = ndb.Key(urlsafe=key)
      crash = key.get()
      crash.ReInitialize(client)
      updated.append(crash)

    ndb.put_multi(updated)

    for crash in updated:
      logging.info('Initialize analysis for crash %s', crash.identifiers)
      if publish_to_client:
        yield CrashWrapperPipeline(client_id, crash.identifiers)
      else:
        yield CrashAnalysisPipeline(client_id, crash.identifiers)
