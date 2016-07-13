# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common.pipeline_wrapper import BasePipeline
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
      targeted_tests=None, suspected_cls=None, force_try_job=False):

    # A list contains tuples of step_names and classified_tests from
    # ProcessSwarmingTaskResultPipeline.
    # The format would be [('step1', {'flaky_tests': ['test1', ..], ..}), ..]
    classified_tests_by_step = []

    if try_job_type == TryJobType.TEST:
      for step_name, base_tests in targeted_tests.iteritems():
        if not base_tests:  # Skip non-swarming tests.
          continue
        # Waits and gets the swarming tasks' results.
        step_future = yield ProcessSwarmingTaskResultPipeline(
            master_name, builder_name, build_number, step_name)
        classified_tests_by_step.append(step_future)

    # Waits until classified_tests_by_step are ready.
    yield RunTryJobForReliableFailurePipeline(
        master_name, builder_name, build_number, good_revision,
        bad_revision, blame_list, try_job_type, compile_targets,
        targeted_tests, suspected_cls, force_try_job,
        *classified_tests_by_step)
