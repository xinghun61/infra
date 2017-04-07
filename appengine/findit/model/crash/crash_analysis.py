# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import hashlib
import json
import logging

from google.appengine.ext import ndb

from crash.crash_report import CrashReport
from gae_libs import appengine_util
from libs import analysis_status
from libs import time_util
from model import triage_status

_FEEDBACK_URL_TEMPLATE = 'https://%s/crash/%s-result-feedback?key=%s'


class CrashAnalysis(ndb.Model):
  """Base class to represent an analysis of a Chrome/Clusterfuzz crash."""
  ################### Properties for the crash itself. ###################
  # In which version or revision of Chrome the crash occurred. Either a version
  # number for Chrome build or a git commit hash/position for chromium build.
  crashed_version = ndb.StringProperty(indexed=False)

  # The parsed ``Stacktrace`` object.
  stacktrace = ndb.PickleProperty(indexed=False)

  # TODO(katesonia): We keep this property because there are many legacy data
  # which only have ``stack_trace`` string, not the parsed ``stacktrace``.
  # Remove this property after we convert those legacy data.
  # The stacktrace string.
  stack_trace = ndb.StringProperty(indexed=False)

  # The signature of the crash.
  signature = ndb.StringProperty(indexed=True)

  # The platform of this crash.
  platform = ndb.StringProperty(indexed=False)

  # Chrome regression range.
  regression_range = ndb.JsonProperty(indexed=False)

  # Dict of ``Dependency``s of ``crashed_version``, which appears in crash stack
  # N.B. ``dependencies`` includes chromium itself.
  dependencies = ndb.PickleProperty(indexed=False)

  # Dict of ``DependencyRoll``s in ``regression_range``, which appears in crash
  # stack. N.B. ``dependencies`` includes chromium itself.
  dependency_rolls = ndb.PickleProperty(indexed=False)

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

  def Initialize(self, crash_data):
    """(Re)Initialize a CrashAnalysis ndb.Model from ``CrashData``.

    This method is only ever called from _NeedsNewAnalysis which is only
    ever called from ScheduleNewAnalysis. It is used for filling in the
    fields of a CrashAnalysis ndb.Model for the first time (though it
    can also be used to re-initialize a given CrashAnalysis). Subclasses
    should extend (not override) this to (re)initialize any
    client-specific fields they may have.
    """
    # Get rid of any previous values there may have been.
    self.Reset()

    # Set the version.
    self.crashed_version = crash_data.crashed_version

    # Set (other) common properties.
    self.stacktrace = crash_data.stacktrace
    self.signature = crash_data.signature
    self.platform = crash_data.platform
    self.regression_range = crash_data.regression_range
    self.dependencies = crash_data.dependencies
    self.dependency_rolls = crash_data.dependency_rolls

    # Set progress properties.
    self.status = analysis_status.PENDING
    self.requested_time = time_util.GetUTCNow()

  def ToCrashReport(self):
    """Converts this model to ``CrashReport`` to give to Predator library."""
    return CrashReport(self.crashed_version, self.signature, self.platform,
                       self.stacktrace, self.regression_range,
                       self.dependencies, self.dependency_rolls)

  @property
  def client_id(self):
    raise NotImplementedError()

  @property
  def feedback_url(self):
    return _FEEDBACK_URL_TEMPLATE % (
        appengine_util.GetDefaultVersionHostname(), self.client_id,
        self.key.urlsafe())

  @property
  def crash_url(self):
    raise NotImplementedError()
