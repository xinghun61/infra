# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.flake.flake_try_job import FlakeTryJob
from model.base_try_job_data import BaseTryJobData


class FlakeTryJobData(BaseTryJobData):
  """Represents a flake try job's metadata."""

  # The key of the original analysis that triggered this flake try job.
  analysis_key = ndb.KeyProperty(indexed=False)

  @ndb.ComputedProperty
  def master_name(self):
    return FlakeTryJob.GetMasterName(self.try_job_key)

  @ndb.ComputedProperty
  def builder_name(self):
    return FlakeTryJob.GetBuilderName(self.try_job_key)

  @ndb.ComputedProperty
  def step_name(self):
    return FlakeTryJob.GetStepName(self.try_job_key)

  @ndb.ComputedProperty
  def test_name(self):
    return FlakeTryJob.GetTestName(self.try_job_key)

  @ndb.ComputedProperty
  def git_hash(self):
    return FlakeTryJob.GetGitHash(self.try_job_key)

  @staticmethod
  def _CreateKey(build_id):  # pragma: no cover
    return ndb.Key('FlakeTryJobData', build_id)

  @staticmethod
  def Create(build_id):  # pragma: no cover
    return FlakeTryJobData(key=FlakeTryJobData._CreateKey(build_id))

  @staticmethod
  def Get(build_id):  # pragma: no cover
    return FlakeTryJobData._CreateKey(build_id).get()
