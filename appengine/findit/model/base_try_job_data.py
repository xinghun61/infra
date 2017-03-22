# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_try_job import BaseTryJob


class BaseTryJobData(ndb.Model):
  """Represents a tryjob's metadata."""

  # When the try job completed.
  end_time = ndb.DateTimeProperty(indexed=True)

  # Error message and reason, if any.
  error = ndb.JsonProperty(indexed=False)

  # Error code if anything went wrong with the try job.
  error_code = ndb.IntegerProperty(indexed=True)

  # The last buildbucket build response received.
  last_buildbucket_response = ndb.JsonProperty(indexed=False, compressed=True)

  # When the try job was created.
  request_time = ndb.DateTimeProperty(indexed=True)

  # When the try job began executing.
  start_time = ndb.DateTimeProperty(indexed=True)

  # The url to the try job build page.
  try_job_url = ndb.StringProperty(indexed=False)

  # An ndb key to the try job entity this data is associated with.
  try_job_key = ndb.KeyProperty(indexed=False)

  # A URL to call back the pipeline monitoring the progress of this tryjob.
  callback_url = ndb.StringProperty(indexed=False)

  # The name of the target for the callback url
  callback_target = ndb.StringProperty(indexed=False)

  @ndb.ComputedProperty
  def master_name(self):  # pragma: no cover
    return BaseTryJob.GetMasterName(self.try_job_key)

  @ndb.ComputedProperty
  def builder_name(self):  # pragma: no cover
    return BaseTryJob.GetBuilderName(self.try_job_key)
