# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from services.compile_failure import compile_try_job
from pipelines.compile_failure import (identify_compile_try_job_culprit_pipeline
                                       as culprit_pipeline)
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.schedule_compile_try_job_pipeline import (
    ScheduleCompileTryJobPipeline)


class StartCompileTryJobPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, failure_info, signals,
          heuristic_result, build_completed, force_try_job):
    """Starts a try job if one is needed for the given compile failure."""
    if not build_completed:  # Only start try-jobs for completed builds.
      return

    try_job_type = failure_type.COMPILE
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info, signals,
        heuristic_result, force_try_job)
    if not need_try_job:
      return

    parameters = compile_try_job.GetParametersToScheduleCompileTryJob(
        master_name, builder_name, build_number, failure_info, signals,
        heuristic_result)
    if not parameters['good_revision']:
      # No last_pass in saved in failure_info.
      return

    try_job_id = yield ScheduleCompileTryJobPipeline(
        master_name, builder_name, build_number, parameters['good_revision'],
        parameters['bad_revision'], try_job_type, parameters['compile_targets'],
        parameters['suspected_revisions'], parameters['cache_name'],
        parameters['dimensions'])

    try_job_result = yield MonitorTryJobPipeline(try_job_key.urlsafe(),
                                                 try_job_type, try_job_id)

    yield culprit_pipeline.IdentifyCompileTryJobCulpritPipeline(
        master_name, builder_name, build_number, try_job_id, try_job_result)
