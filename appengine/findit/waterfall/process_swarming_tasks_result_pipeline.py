# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from services.test_failure import ci_test_failure
from waterfall.process_swarming_task_result_pipeline import (
    ProcessSwarmingTaskResultPipeline)
from waterfall.update_analysis_with_flake_info_pipeline import (
    UpdateAnalysisWithFlakeInfoPipeline)


class ProcessSwarmingTasksResultPipeline(BasePipeline):
  """Root Pipeline to process results of swarming reruns."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, failure_info,
          build_completed):
    task_results = []

    # Waits for build to complete to process the results of swarming reruns.
    if not build_completed or failure_info['failure_type'] != failure_type.TEST:
      return

    for step_name, step_failure in failure_info['failed_steps'].iteritems():
      step_has_first_time_failure = ci_test_failure.AnyTestHasFirstTimeFailure(
          step_failure.get('tests') or {}, build_number)
      if not step_has_first_time_failure:
        continue
      task_result = yield ProcessSwarmingTaskResultPipeline(
          master_name, builder_name, build_number, step_name)
      task_results.append(task_result)

    yield UpdateAnalysisWithFlakeInfoPipeline(master_name, builder_name,
                                              build_number, *task_results)
