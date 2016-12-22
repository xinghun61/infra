# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model import analysis_status


class BaseTryJob(ndb.Model):
  """Represents a base try job result."""

  # The status of the try job.
  status = ndb.IntegerProperty(
      default=analysis_status.PENDING, indexed=False)

  # A list of try job IDs associated with each try job for collecting metadata.
  try_job_ids = ndb.JsonProperty(indexed=False, compressed=True)

  @property
  def completed(self):
    return self.status in (
        analysis_status.COMPLETED, analysis_status.ERROR)

  @property
  def failed(self):
    return self.status == analysis_status.ERROR
