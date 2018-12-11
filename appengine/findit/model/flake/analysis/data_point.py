# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64

from google.appengine.ext import ndb


class DataPoint(ndb.Model):
  # TODO(crbug.com/809218): Deprecate fields that refer to 'build.'

  # Indexed properties for querying for nearby data points when appropriate in
  # case an exact match can't be found.

  # The name of the gitiles project, e.g. 'chromium/src'
  gitiles_project = ndb.StringProperty(indexed=True)

  # the name of the buildbucket, e.g. 'ci',
  bucket = ndb.StringProperty(indexed=True)

  # The name of the builder that surfaced the flaky test.
  builder_name = ndb.StringProperty(indexed=True)

  # The build number corresponding to this data point. Only relevant for
  # analysis at the build level.
  build_number = ndb.IntegerProperty(indexed=False)

  # The name of the step that the flaky test occurred on.
  step_name = ndb.StringProperty(indexed=True)

  # The name of the flaky test.
  test_name = ndb.StringProperty(indexed=True)

  # The commit position of this data point.
  commit_position = ndb.IntegerProperty(indexed=True)

  # The timestamp the commit position was landed.
  commit_timestamp = ndb.DateTimeProperty(indexed=True)

  # The name of the master that the flaky test was found on for pre-LUCI builds.
  legacy_master_name = ndb.StringProperty(indexed=False)

  # The url to the build page of the build whose artifacts were used to generate
  # This data point.
  build_url = ndb.StringProperty(indexed=False)

  # The pass rate of the test when run against this commit.
  # -1 means that the test doesn't exist at this commit/build.
  pass_rate = ndb.FloatProperty(indexed=False)

  # The ID of the swarming task responsible for generating this data.
  task_ids = ndb.StringProperty(indexed=False, repeated=True)

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
             commit_timestamp=None,
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
    data_point.commit_timestamp = commit_timestamp
    return data_point

  @classmethod
  def _CreateKey(cls, gitiles_project, bucket, builder_name, step_name,
                 test_name, git_hash):
    encoded_gitiles_project = base64.urlsafe_b64encode(gitiles_project)
    encoded_test_name = base64.urlsafe_b64encode(test_name)
    return ndb.Key(
        cls, '/'.join([
            encoded_gitiles_project, bucket, builder_name, step_name,
            encoded_test_name, git_hash
        ]))

  @classmethod
  def Get(cls, gitiles_project, bucket, builder_name, step_name, test_name,
          git_hash):
    return cls._CreateKey(gitiles_project, bucket, builder_name, step_name,
                          test_name, git_hash).get()

  @classmethod
  def CreateAndSave(cls,
                    gitiles_project,
                    bucket,
                    builder_name,
                    step_name,
                    test_name,
                    git_hash,
                    legacy_master_name=None,
                    build_number=None,
                    build_url=None,
                    pass_rate=None,
                    task_ids=None,
                    commit_position=None,
                    try_job_url=None,
                    iterations=None,
                    elapsed_seconds=0,
                    error=None,
                    commit_timestamp=None,
                    failed_swarming_task_attempts=0):
    """Creates a data point, saves it to ndb, and returns it."""
    data_point = cls(
        key=cls._CreateKey(gitiles_project, bucket, builder_name, step_name,
                           test_name, git_hash),
        gitiles_project=gitiles_project,
        bucket=bucket,
        builder_name=builder_name,
        step_name=step_name,
        test_name=test_name,
        legacy_master_name=legacy_master_name,
        build_url=build_url,
        build_number=build_number,
        pass_rate=pass_rate,
        task_ids=task_ids or [],
        git_hash=git_hash,
        commit_position=commit_position if commit_position is not None else -1,
        try_job_url=try_job_url,
        iterations=iterations,
        elapsed_seconds=elapsed_seconds,
        error=error,
        failed_swarming_task_attempts=failed_swarming_task_attempts,
        commit_timestamp=commit_timestamp,
    )

    data_point.put()
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
