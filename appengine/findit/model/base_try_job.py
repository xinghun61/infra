# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import analysis_status


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

  @classmethod
  def GetMasterName(cls, key):
    return key.pairs()[0][1].split('/')[0]

  @classmethod
  def GetBuilderName(cls, key):
    return key.pairs()[0][1].split('/')[1]

  @ndb.ComputedProperty
  def master_name(self):
    return self.GetMasterName(self.key)

  @ndb.ComputedProperty
  def builder_name(self):
    return self.GetBuilderName(self.key)
