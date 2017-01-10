# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from waterfall import waterfall_config
from waterfall.schedule_try_job_pipeline import ScheduleTryJobPipeline


class ScheduleFlakeTryJobPipeline(ScheduleTryJobPipeline):
  """A pipeline for scheduling a new flake try job for a flaky test."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def _GetBuildProperties(
      self, master_name, builder_name, step_name, test_name, git_hash):
    iterations = waterfall_config.GetCheckFlakeSettings().get(
        'iterations_to_rerun')

    return {
        'recipe': 'findit/chromium/flake',
        'target_mastername': master_name,
        'target_testername': builder_name,
        'test_revision': git_hash,
        'test_repeat_count': iterations,
        'tests': {
            step_name: [test_name]
        }
    }

  def _CreateTryJobData(self, build_id, try_job_key):
    try_job_data = FlakeTryJobData.Create(build_id)
    try_job_data.try_job_key = try_job_key
    try_job_data.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, step_name, test_name, git_hash):
    """Triggers a flake try job.

    Args:
      master_name (str): The master name of a flaky test.
      builder_name (str): The builder name of a flaky test.
      step_name (str): The name of the step the flaky test occurred on.
      test_name (str): The name of the flaky test.
      git_hash (str): The git hash of the revision to run the try job against.

    Returns:
      build_id (str): Id of the triggered try job.
    """
    properties = self._GetBuildProperties(
        master_name, builder_name, step_name, test_name, git_hash)
    build_id = self._TriggerTryJob(master_name, builder_name, properties, {})

    try_job = FlakeTryJob.Get(
        master_name, builder_name, step_name, test_name, git_hash)
    try_job.flake_results.append({'try_job_id': build_id})
    try_job.try_job_ids.append(build_id)
    try_job.put()

    # Create a corresponding Flake entity to capture as much metadata as early
    # as possible.
    self._CreateTryJobData(build_id, try_job.key)

    return build_id
