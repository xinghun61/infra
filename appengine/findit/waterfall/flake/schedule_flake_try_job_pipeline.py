# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import pipeline
from gae_libs.pipeline_wrapper import BasePipeline
from common.waterfall import failure_type
from services import try_job as try_job_service
from services.flake_failure import flake_try_job
from waterfall import waterfall_config


class ScheduleFlakeTryJobPipeline(BasePipeline):
  """A pipeline for scheduling a new flake try job for a flaky test."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self,
          master_name,
          builder_name,
          canonical_step_name,
          test_name,
          git_hash,
          urlsafe_analysis_key,
          cache_name,
          dimensions,
          iterations_to_rerun=None):
    """Triggers a flake try job.

    Args:
      master_name (str): The master name of a flaky test.
      builder_name (str): The builder name of a flaky test.
      canonical_step_name (str): The canonical name of the step the flaky test
          occurred on.
      test_name (str): The name of the flaky test.
      git_hash (str): The git hash of the revision to run the try job against.
      urlsafe_analysis_key (str): The urlsafe key of the original
          MasterFlakeAnalysis that triggered this try job.
      cache_name (str): A string to identify separate directories for different
          waterfall bots on the trybots.
      dimensions (list): A list of strings in the format
          ["key1:value1", "key2:value2"].
      iterations_to_rerun (int): The number of iterations to rerun.

    Returns:
      build_id (str): Id of the triggered try job.
    """
    properties = flake_try_job.GetBuildProperties(
        master_name, builder_name, canonical_step_name, test_name, git_hash,
        iterations_to_rerun)
    tryserver_mastername, tryserver_buildername = (
        waterfall_config.GetFlakeTrybot(
            master_name, builder_name, force_buildbot=False))
    build_id, error = try_job_service.TriggerTryJob(
        master_name, builder_name, tryserver_mastername, tryserver_buildername,
        properties, {},
        failure_type.GetDescriptionForFailureType(failure_type.FLAKY_TEST),
        cache_name, dimensions, self.pipeline_id)

    if error:  # pragma: no cover
      raise pipeline.Retry('Error "%s" occurred. Reason: "%s"' % (error.message,
                                                                  error.reason))

    try_job = flake_try_job.UpdateTryJob(master_name, builder_name,
                                         canonical_step_name, test_name,
                                         git_hash, build_id)

    # Create a corresponding Flake entity to capture as much metadata as early
    # as possible.
    flake_try_job.CreateTryJobData(build_id, try_job.key, urlsafe_analysis_key)

    return build_id
