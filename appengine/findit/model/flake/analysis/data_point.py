# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class DataPoint(ndb.Model):
  # TODO(crbug.com/809218): Deprecate fields that refer to 'build.'

  # The build number corresponding to this data point. Only relevant for
  # analysis at the build level.
  build_number = ndb.IntegerProperty(indexed=False)

  # The url to the build page of the build whose artifacts were used to generate
  # This data point.
  build_url = ndb.StringProperty(indexed=False)

  # The pass rate of the test when run against this commit.
  # -1 means that the test doesn't exist at this commit/build.
  pass_rate = ndb.FloatProperty(indexed=False)

  # The ID of the swarming task responsible for generating this data.
  task_ids = ndb.StringProperty(indexed=False, repeated=True)

  # The commit position of this data point.
  commit_position = ndb.IntegerProperty(indexed=False)

  # The timestamp the commit position was landed. Used for display purposes
  # only.
  commit_position_landed_time = ndb.DateTimeProperty(indexed=False)

  # The git hash of this data point.
  git_hash = ndb.StringProperty(indexed=False)

  # Any errors associated with generating this data point.
  error = ndb.JsonProperty(indexed=False)

  # The URL to the try job that generated this data point, if any.
  try_job_url = ndb.StringProperty(indexed=False)

  # The number of iterations run to determine this data point's pass rate.
  iterations = ndb.IntegerProperty(indexed=False)

  # The total seconds that these iterations took to compute.
  elapsed_seconds = ndb.IntegerProperty(indexed=False, default=0)

  # The number of times a swarming task had an error while generating this
  # data point.
  failed_swarming_task_attempts = ndb.IntegerProperty(indexed=False, default=0)

  @staticmethod
  def Create(build_number=None,
             build_url=None,
             pass_rate=None,
             task_ids=None,
             commit_position=None,
             git_hash=None,
             try_job_url=None,
             iterations=None,
             elapsed_seconds=0,
             error=None,
             commit_position_landed_time=None,
             failed_swarming_task_attempts=0):
    data_point = DataPoint()
    data_point.build_url = build_url
    data_point.build_number = build_number
    data_point.pass_rate = pass_rate
    task_ids = task_ids or []
    data_point.task_ids = task_ids
    data_point.commit_position = commit_position
    data_point.git_hash = git_hash
    data_point.try_job_url = try_job_url
    data_point.iterations = iterations
    data_point.elapsed_seconds = elapsed_seconds
    data_point.error = error
    data_point.failed_swarming_task_attempts = failed_swarming_task_attempts
    data_point.commit_position_landed_time = commit_position_landed_time
    return data_point

  def GetPassCount(self):
    """Computes the number of iterations that passed given a DataPoint."""
    if self.pass_rate is None or self.iterations is None:
      # Can't compute, so return None.
      return None

    if self.pass_rate < 0:
      # Test doesn't exist.
      return 0

    return int(round(self.pass_rate * self.iterations))

  def GetSwarmingTaskId(self):
    """Returns the last swarming task in the list.

      Designed to be used to surface a representative swarming task of
      flakiness. Because Flake Analyzer always moves on as soon as a data point
      is measured to be flaky, as long as the flakiness is reproducible the
      last swarming task is guaranteed to be representative of an instance of
      flakiness.
    """
    # TODO(crbug.com/884375): Find the task id that best represents flakiness
    # in case the last one doesn't have any failures (expected to be rare).
    return self.task_ids[-1] if self.task_ids else None
