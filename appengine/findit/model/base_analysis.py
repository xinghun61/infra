# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import analysis_status


class BaseAnalysis(ndb.Model):
  """Represents a build analysis of a builder in a Chromium waterfall."""

  @property
  def completed(self):
    return self.status in (
        analysis_status.COMPLETED, analysis_status.ERROR)

  @property
  def duration(self):
    if not self.completed or not self.end_time or not self.start_time:
      return None

    return int((self.end_time - self.start_time).total_seconds())

  @property
  def failed(self):
    return self.status == analysis_status.ERROR

  @property
  def status_description(self):
    return analysis_status.STATUS_TO_DESCRIPTION.get(self.status, 'Unknown')

  def Reset(self):
    self.pipeline_status_path = None
    self.status = analysis_status.PENDING
    self.request_time = None
    self.start_time = None
    self.end_time = None
    self.version = None

  # The url path to the pipeline status page.
  pipeline_status_path = ndb.StringProperty(indexed=False)

  # The status of the analysis.
  status = ndb.IntegerProperty(default=analysis_status.PENDING, indexed=False)
  # When the analysis was requested.
  request_time = ndb.DateTimeProperty(indexed=True)
  # When the analysis actually started.
  start_time = ndb.DateTimeProperty(indexed=False)
  # When the analysis actually ended.
  end_time = ndb.DateTimeProperty(indexed=False)
  # When the analysis was updated.
  updated_time = ndb.DateTimeProperty(indexed=False, auto_now=True)
  # Record which version of analysis.
  version = ndb.StringProperty(indexed=False)
