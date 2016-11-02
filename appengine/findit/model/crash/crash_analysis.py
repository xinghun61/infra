# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import hashlib
import json
import logging

from google.appengine.ext import ndb

from common import appengine_util
from crash.type_enums import CrashClient
from model import analysis_status
from model import triage_status

# TODO(katesonia): Move this to fracas config.
_FINDIT_FRACAS_FEEDBACK_URL_TEMPLATE = '%s/crash/fracas-result-feedback?key=%s'

class CrashAnalysis(ndb.Model):
  """Base class to represent an analysis of a Chrome/Clusterfuzz crash."""
  ################### Properties for the crash itself. ###################
  # In which version or revision of Chrome the crash occurred. Either a version
  # number for Chrome build or a git commit hash/position for chromium build.
  crashed_version = ndb.StringProperty(indexed=False)

  # The stack_trace_string.
  stack_trace = ndb.StringProperty(indexed=False)

  # The signature of the crash.
  signature = ndb.StringProperty(indexed=False)

  # The platform of this crash.
  platform = ndb.StringProperty(indexed=False)

  # ID to differentiate different client.
  client_id = ndb.StringProperty(indexed=False)

  # Chrome regression range.
  regression_range = ndb.JsonProperty(indexed=False)

  ################### Properties for the analysis progress. ###################

  # The url path to the pipeline status page.
  pipeline_status_path = ndb.StringProperty(indexed=False)

  # The status of the analysis.
  status = ndb.IntegerProperty(
      default=analysis_status.PENDING, indexed=False)

  # When the analysis was requested.
  requested_time = ndb.DateTimeProperty(indexed=True)

  # When the analysis was started.
  started_time = ndb.DateTimeProperty(indexed=False)

  # When the analysis was completed.
  completed_time = ndb.DateTimeProperty(indexed=False)

  # Which version of findit produces this result.
  findit_version = ndb.StringProperty(indexed=False)

  ################### Properties for the analysis result. ###################

  solution = ndb.StringProperty(indexed=True)  # 'core', 'blame', etc.

  # Analysis results.
  result = ndb.JsonProperty(compressed=True, indexed=False)

  # Flag to check whether there is a result.
  has_regression_range = ndb.BooleanProperty(indexed=True)
  found_suspects = ndb.BooleanProperty(indexed=True)
  found_project = ndb.BooleanProperty(indexed=True)
  found_components = ndb.BooleanProperty(indexed=True)

  # Correct results.
  culprit_regression_range = ndb.JsonProperty(indexed=False)
  culprit_cls = ndb.JsonProperty(indexed=False)
  culprit_components = ndb.JsonProperty(indexed=False)
  culprit_project = ndb.StringProperty(indexed=False)

  # Triage status - 'Untriaged', 'Incorrect', 'Correct', 'Unsure'.
  regression_range_triage_status = ndb.IntegerProperty(
      indexed=True, default=triage_status.UNTRIAGED)
  suspected_cls_triage_status = ndb.IntegerProperty(
      indexed=True, default=triage_status.UNTRIAGED)
  suspected_components_triage_status = ndb.IntegerProperty(
      indexed=True, default=triage_status.UNTRIAGED)
  suspected_project_triage_status = ndb.IntegerProperty(
      indexed=True, default=triage_status.UNTRIAGED)

  triage_history = ndb.JsonProperty(indexed=False)

  # Triage note.
  note = ndb.StringProperty(indexed=False)

  def Reset(self):
    self.pipeline_status_path = None
    self.status = analysis_status.PENDING
    self.requested_time = None
    self.started_time = None
    self.completed_time = None
    self.findit_version = None
    self.has_regression_range = None
    self.found_suspects = None
    self.solution = None
    self.result = None
    self.regression_range_triage_status = triage_status.UNTRIAGED
    self.culprit_regression_range = None
    self.suspected_cls_triage_status = triage_status.UNTRIAGED
    self.culprit_cls = None
    self.suspected_project_triage_status = triage_status.UNTRIAGED
    self.culprit_project = None
    self.suspected_components_triage_status = triage_status.UNTRIAGED
    self.culprit_components = None
    self.triage_history = None
    self.note = None

  def Update(self, update):
    updated = False
    for key, value in update.iteritems():
      if not hasattr(self, key):
        continue

      setattr(self, key, value)
      updated = True

    return updated

  @property
  def completed(self):
    return self.status in (
        analysis_status.COMPLETED, analysis_status.ERROR)

  @property
  def failed(self):
    return self.status == analysis_status.ERROR

  @property
  def duration(self):
    if not self.completed:
      return None

    return int((self.completed_time - self.started_time).total_seconds())

  @classmethod
  def _CreateKey(cls, crash_identifiers):
    return ndb.Key(cls.__name__, hashlib.sha1(
        json.dumps(crash_identifiers, sort_keys=True)).hexdigest())

  @classmethod
  def Get(cls, crash_identifiers):
    return cls._CreateKey(crash_identifiers).get()

  @classmethod
  def Create(cls, crash_identifiers):
    return cls(key=cls._CreateKey(crash_identifiers))

  def ToPublishableResult(self, crash_identifiers):
    """Convert this datastore analysis into a publishable result.

    Args:
      crash_identifiers (dict): ??

    Returns:
      A dict of the given ``crash_identifiers``, this model's
      ``client_id``, and a publishable version of this model's ``result``.
    """
    result = copy.deepcopy(self.result)
    client_id = self.client_id

    # TODO(katesonia): move this to ChromeCrashAnalysis
    if (client_id == CrashClient.FRACAS or
        client_id == CrashClient.CRACAS):
      result['feedback_url'] = _FINDIT_FRACAS_FEEDBACK_URL_TEMPLATE % (
          appengine_util.GetDefaultVersionHostname(), self.key.urlsafe())
      if result['found'] and 'suspected_cls' in result:
        for cl in result['suspected_cls']:
          cl['confidence'] = round(cl['confidence'], 2)
          cl.pop('reason', None)
    elif client_id == CrashClient.CLUSTERFUZZ:  # pragma: no cover.
      # TODO(katesonia): Post process clusterfuzz model result if needed.
      pass

    logging.info('Publish result:\n%s',
                 json.dumps(result, indent=4, sort_keys=True))
    return {
        'crash_identifiers': crash_identifiers,
        'client_id': client_id,
        'result': result,
    }
