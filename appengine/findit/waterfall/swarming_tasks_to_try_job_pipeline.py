# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from pipeline_wrapper import BasePipeline
from waterfall.process_swarming_task_result_pipeline import (
    ProcessSwarmingTaskResultPipeline)
from waterfall.run_try_job_for_reliable_failure_pipeline import (
    RunTryJobForReliableFailurePipeline)
from waterfall.trigger_swarming_task_pipeline import TriggerSwarmingTaskPipeline
from waterfall.try_job_type import TryJobType


class SwarmingTasksToTryJobPipeline(BasePipeline):
  """Root Pipeline to start swarming tasks and possible try job on the build."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, blame_list, try_job_type, compile_targets=None,
      targeted_tests=None):

    # A list contains tuples of step_names and tests_statuses from
    # ProcessSwarmingTaskResultPipeline.
    # The format would be [('step1', {'test1': {'total_run': 3, ..}, ..}), ..]
    steps_statuses = []

    if try_job_type == TryJobType.TEST:
      for step_name, tests in targeted_tests.iteritems():
        task_id = yield TriggerSwarmingTaskPipeline(
            master_name, builder_name, build_number, step_name, tests)
        step_future = yield ProcessSwarmingTaskResultPipeline(
            master_name, builder_name, build_number, step_name, task_id)
        steps_statuses.append(step_future)

   # Waits until steps_statuses are ready.
    yield RunTryJobForReliableFailurePipeline(
        master_name, builder_name, build_number, good_revision,
        bad_revision, blame_list, try_job_type, compile_targets, targeted_tests,
        *steps_statuses)
