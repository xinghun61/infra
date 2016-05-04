# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model import analysis_status


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

  # Analysis results.
  result = ndb.JsonProperty(compressed=True, indexed=False)

  # Tags for query and monitoring.
  has_regression_range = ndb.BooleanProperty(indexed=True)
  found_suspects = ndb.BooleanProperty(indexed=True)
  solution = ndb.StringProperty(indexed=True)  # 'core', 'blame', etc.

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
