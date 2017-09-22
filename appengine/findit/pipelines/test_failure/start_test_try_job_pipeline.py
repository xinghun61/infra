# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from services.test_failure import test_try_job
from waterfall.identify_try_job_culprit_pipeline import (
    IdentifyTryJobCulpritPipeline)
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.schedule_test_try_job_pipeline import (
    ScheduleTestTryJobPipeline)


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
    if not parameters['good_revision']:
      # No last_pass in saved in failure_info.
      return

    try_job_id = yield ScheduleTestTryJobPipeline(
        master_name, builder_name, build_number, parameters['good_revision'],
        parameters['bad_revision'], try_job_type,
        parameters['suspected_revisions'], parameters['cache_name'],
        parameters['dimensions'], parameters['task_results'])

    try_job_result = yield MonitorTryJobPipeline(try_job_key.urlsafe(),
                                                 try_job_type, try_job_id)

    yield IdentifyTryJobCulpritPipeline(master_name, builder_name, build_number,
                                        try_job_type, try_job_id,
                                        try_job_result)
