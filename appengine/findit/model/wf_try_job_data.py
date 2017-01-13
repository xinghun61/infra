# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_try_job_data import BaseTryJobData
from model.wf_try_job import WfTryJob


class WfTryJobData(BaseTryJobData):
  """Represents a tryjob's data for a completed compile or test try job."""
  # Number of commits in the revision range.
  regression_range_size = ndb.IntegerProperty(indexed=False)

  # Number of commits analyzed to determine a culprit, if any.
  number_of_commits_analyzed = ndb.IntegerProperty(indexed=False)

  # Culprit(s) determined to have caused the failure, if any.
  culprits = ndb.JsonProperty(indexed=False)

  # Whether or not the try job had compile targets passed (compile only).
  has_compile_targets = ndb.BooleanProperty(indexed=True)

  # Whether or not the try job had heuristic results to guide it.
  has_heuristic_results = ndb.BooleanProperty(indexed=True)

  # The type of try job, such as 'compile' or 'test'.
  try_job_type = ndb.StringProperty(indexed=True)

  @ndb.ComputedProperty
  def build_number(self):
    return WfTryJob.GetBuildNumber(self.try_job_key)

  @staticmethod
  def _CreateKey(build_id):  # pragma: no cover
    return ndb.Key('WfTryJobData', build_id)

  @staticmethod
  def Create(build_id):  # pragma: no cover
    return WfTryJobData(key=WfTryJobData._CreateKey(build_id))

  @staticmethod
  def Get(build_id):  # pragma: no cover
    return WfTryJobData._CreateKey(build_id).get()
