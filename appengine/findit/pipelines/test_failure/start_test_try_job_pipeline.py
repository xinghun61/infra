# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from pipelines.test_failure.identify_test_try_job_culprit_pipeline import (
    IdentifyTestTryJobCulpritPipeline)
from pipelines.test_failure.schedule_test_try_job_pipeline import (
    ScheduleTestTryJobPipeline)
from services.test_failure import test_try_job
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline


class StartTestTryJobPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, failure_info,
          heuristic_result, build_completed, force_try_job):
    """Starts a try job if one is needed for the given test failure."""
    if not build_completed:  # Only start try-jobs for completed builds.
      return

    try_job_type = failure_type.TEST

    # Gets the swarming tasks' results.
    need_try_job, try_job_key = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, heuristic_result,
        force_try_job)
    if not need_try_job:
      return

    parameters = test_try_job.GetParametersToScheduleTestTryJob(
        master_name, builder_name, build_number, failure_info, heuristic_result)
    if not parameters.good_revision:
      # No last_pass in saved in failure_info.
      return

    if not parameters.targeted_tests:
      logging.info('All tests are flaky, no try job will be triggered.')
      return

    try_job_id = yield ScheduleTestTryJobPipeline(parameters)

    try_job_result = yield MonitorTryJobPipeline(try_job_key.urlsafe(),
                                                 try_job_type, try_job_id)

    yield IdentifyTestTryJobCulpritPipeline(
        master_name, builder_name, build_number, try_job_id, try_job_result)
