# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.start_waterfall_try_job_inputs import StartCompileTryJobInput
from gae_libs import pipelines
from gae_libs.pipelines import GeneratorPipeline
from services.compile_failure import compile_try_job
from pipelines.compile_failure import (identify_compile_try_job_culprit_pipeline
                                       as culprit_pipeline)
from pipelines.compile_failure.run_compile_try_job_pipeline import (
    RunCompileTryJobPipeline)
from services.parameters import IdentifyCompileTryJobCulpritParameters


class StartCompileTryJobPipeline(GeneratorPipeline):
  input_type = StartCompileTryJobInput

  def RunImpl(self, pipeline_input):
    """Starts a try job if one is needed for the given compile failure."""
    if not pipeline_input.build_completed:
      # Only start try-jobs for completed builds.
      return

    need_try_job, urlsafe_try_job_key = compile_try_job.NeedANewCompileTryJob(
        pipeline_input)
    if not need_try_job:
      return

    parameters = compile_try_job.GetParametersToScheduleCompileTryJob(
        pipeline_input, urlsafe_try_job_key)
    if not parameters.good_revision:
      # No last_pass in saved in failure_info.
      return

    try_job_result = yield RunCompileTryJobPipeline(parameters)

    identify_culprit_input = pipelines.CreateInputObjectInstance(
        IdentifyCompileTryJobCulpritParameters,
        build_key=pipeline_input.build_key,
        result=try_job_result)
    yield culprit_pipeline.IdentifyCompileTryJobCulpritPipeline(
        identify_culprit_input)
