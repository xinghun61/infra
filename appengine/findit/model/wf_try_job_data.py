# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class WfTryJobData(ndb.Model):
  """Represents a tryjob's data for a completed try job."""
  # The original master on which the build was detected to have failed.
  master_name = ndb.StringProperty(indexed=True)
  # The original buildername on which the build was detected to have failed.
  builder_name = ndb.StringProperty(indexed=True)
  # The type of try job, such as 'compile' or 'test'.
  try_job_type = ndb.StringProperty(indexed=True)
  # When the try job was created.
  request_time = ndb.DateTimeProperty(indexed=True)
  # When the try job began executing.
  start_time = ndb.DateTimeProperty(indexed=True)
  # When the try job completed.
  end_time = ndb.DateTimeProperty(indexed=True)
  # Number of commits in the revision range.
  regression_range_size = ndb.IntegerProperty(indexed=False)
  # Number of commits analyzed to determine a culprit if any.
  number_of_commits_analyzed = ndb.IntegerProperty(indexed=False)
  # Culprit(s) determined to have caused the failure, if any.
  culprits = ndb.JsonProperty(indexed=False)
  # The url to the try job build page.
  try_job_url = ndb.StringProperty(indexed=False)
  # Error message and reason, if any.
  error = ndb.JsonProperty(indexed=False)

  # TODO(lijeffrey): We may want to determine whether or not a try job
  # was triggered as a redo of another if the first failed to find a culprit.
  # For example, if passing compile targets yields no results, a redo without
  # compile targets may be attempted to find the culprit CL and the occurrence
  # documented in a queryable manner.

  @staticmethod
  def _CreateKey(build_id):  # pragma: no cover
    return ndb.Key('WfTryJobData', build_id)

  @staticmethod
  def Create(build_id):  # pragma: no cover
    return WfTryJobData(key=WfTryJobData._CreateKey(build_id))

  @staticmethod
  def Get(build_id):  # pragma: no cover
    return WfTryJobData._CreateKey(build_id).get()

