# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import cloudstorage as gcs
import hashlib
import json

from google.appengine.ext import ndb

from analysis.constants import CHROMIUM_REPO_URL
from analysis.constants import CHROMIUM_ROOT_PATH
from analysis.crash_report import CrashReport
from common.model.log import Log
from common.model import triage_status
from gae_libs import appengine_util
from libs import analysis_status
from libs import time_util

_FEEDBACK_URL_TEMPLATE = 'https://%s/%s/result-feedback?key=%s'
_CLOUD_STORAGE_MARKER = 'Google storage stacktrace:'
# If the entity size is greater than ~1MB, we'll hit an exception.
# Some fields can be very large, so we limit them to 800KB.
_PROPERTY_MAXIMUM_SIZE = 800000
_STORAGE_PATH = '/big_stacktrace'
_BACKOFF_FACTOR = 1.1


class CrashAnalysis(ndb.Model):
  """Base class to represent an analysis of a Chrome/Clusterfuzz crash."""
  ################### Properties for the crash itself. ###################
  # In which version or revision of Chrome the crash occurred. Either a version
  # number for Chrome build or a git commit hash/position for chromium build.
  crashed_version = ndb.StringProperty(indexed=False)

  # The parsed ``Stacktrace`` object.
  stacktrace = ndb.PickleProperty(indexed=False)

  # The raw stacktrace string sent by client. Note, if the raw stacktrace is
  # bigger than 1MB, it cannot be put into datastore, in this case, we will
  # store it to google storage.
  stacktrace_str = ndb.StringProperty(indexed=False)

  # The signature of the crash.
  signature = ndb.StringProperty(indexed=True)

  # The platform of this crash.
  platform = ndb.StringProperty()

  # Chrome regression range.
  regression_range = ndb.JsonProperty(indexed=False)

  # Dict of ``Dependency``s of ``crashed_version``, which appears in crash stack
  # N.B. ``dependencies`` includes chromium itself.
  dependencies = ndb.PickleProperty(indexed=False)

  # Dict of ``DependencyRoll``s in ``regression_range``, which appears in crash
  # stack. N.B. ``dependencies`` includes chromium itself.
  dependency_rolls = ndb.PickleProperty(indexed=False)

  identifiers = ndb.JsonProperty(indexed=False)

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

  # Which version of predator produces this result.
  predator_version = ndb.StringProperty(indexed=False)

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
    self.started_time = None
    self.completed_time = None
    self.predator_version = None
    self.has_regression_range = None
    self.found_suspects = None
    self.solution = None
    self.result = None
    self.regression_range_triage_status = triage_status.UNTRIAGED
    self.suspected_cls_triage_status = triage_status.UNTRIAGED
    self.suspected_project_triage_status = triage_status.UNTRIAGED
    self.suspected_components_triage_status = triage_status.UNTRIAGED

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

  @property
  def stack_trace(self):
    if (not self.stacktrace_str or
        not self.stacktrace_str.startswith(_CLOUD_STORAGE_MARKER)):
      return self.stacktrace_str

    stack_trace_file_path = self.stacktrace_str[len(_CLOUD_STORAGE_MARKER):]
    with gcs.open(stack_trace_file_path) as f:
      return f.read()

  @stack_trace.setter
  def stack_trace(self, raw_stacktrace):
    if not raw_stacktrace or len(raw_stacktrace) < _PROPERTY_MAXIMUM_SIZE:
      self.stacktrace_str = raw_stacktrace
      return

    # The maximum size of a property to be put to datastore is 1MB, write the
    # big stacktrace to cloud storage instead.
    file_name = self.key.urlsafe()
    stack_trace_file_path = '%s/%s' % (_STORAGE_PATH, file_name)
    self.stacktrace_str = '%s%s' % (_CLOUD_STORAGE_MARKER,
                                    stack_trace_file_path)
    with gcs.open(
        stack_trace_file_path, 'w', content_type='text/plain',
        retry_params=gcs.RetryParams(backoff_factor=_BACKOFF_FACTOR)) as f:
      f.write(str(raw_stacktrace))

  @property
  def log(self):
    return Log.Get(self.identifiers)

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

    self.stack_trace = crash_data.raw_stacktrace
    self.stacktrace = crash_data.stacktrace
    self.signature = crash_data.signature
    self.platform = crash_data.platform
    self.regression_range = crash_data.regression_range
    self.dependencies = crash_data.dependencies
    self.dependency_rolls = crash_data.dependency_rolls
    self.identifiers = crash_data.identifiers

    # Set progress properties.
    self.status = analysis_status.PENDING
    self.requested_time = time_util.GetUTCNow()
    self.started_time = time_util.GetUTCNow()

  def ToCrashReport(self):
    """Converts this model to ``CrashReport`` to give to Predator library."""
    return CrashReport(self.crashed_version, self.signature, self.platform,
                       self.stacktrace, self.regression_range,
                       self.dependencies, self.dependency_rolls,
                       self.root_repo_url, self.root_repo_path)

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

  @property
  def root_repo_url(self):
    return CHROMIUM_REPO_URL

  @property
  def root_repo_path(self):
    return CHROMIUM_ROOT_PATH

  def ToJson(self):
    # ``stack_trace`` is the raw stacktrace string, ``stacktrace`` is the parsed
    # ``Stactrace`` object. We want to get the raw string. However some legacy
    # data didn't store any, in this case, we use ``self.stacktrace.ToString()``
    # instead.
    raw_stacktrace = self.stack_trace or (
        self.stacktrace.ToString() if self.stacktrace else None)

    return {
        'signature': self.signature,
        'platform': self.platform,
        'stack_trace': raw_stacktrace
    }

  def ReInitialize(self, client):
    """ReInitializes the ``CrashAnalysis`` entity.

    Note, there are 3 parts of ``CrashAnalysis`` that will be kept the same:
    1. raw data returned by ``ToJson``.
    2. ``requested_time`` (namely, the datetime when this crash was first sent
    to Predator).
    3. all manually collected ``culprit_*`` results, ``triage_history`` and
    ``note``.

    Other properties like parsed ``stacktrace`` or ``dependencies`` will be
    recomputed.
    """
    crash_json = self.ToJson()
    crash_data = client.GetCrashData(crash_json)

    # The requested time is the first time the crash was requested by users,
    # we should keep the same requested time when we do rerun.
    requested_time = self.requested_time
    self.Reset()
    self.Initialize(crash_data)
    self.requested_time = requested_time
