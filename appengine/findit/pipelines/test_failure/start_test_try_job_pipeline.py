# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import monitoring
from dto.start_waterfall_try_job_inputs import StartTestTryJobInputs
from gae_libs.pipelines import GeneratorPipeline
from pipelines.test_failure.identify_test_try_job_culprit_pipeline import (
    IdentifyTestTryJobCulpritPipeline)
from pipelines.test_failure.run_test_try_job_pipeline import (
    RunTestTryJobPipeline)
from services.parameters import IdentifyTestTryJobCulpritParameters
from services.test_failure import test_try_job


class StartTestTryJobPipeline(GeneratorPipeline):

  input_type = StartTestTryJobInputs

  def OnAbort(self, pipeline_input):
    if pipeline_input.heuristic_result.heuristic_result is None:
      # This is a resumed try job pipeline after heuristic analysis aborted,
      # but this pipeline also aborted, we need to add metrics at this case.
      monitoring.aborted_pipelines.increment({'type': 'test'})

  def RunImpl(self, start_test_try_job_inputs):
    """Starts a try job if one is needed for the given test failure."""
    need_try_job, parameters = test_try_job.GetInformationToStartATestTryJob(
        start_test_try_job_inputs)
    if not need_try_job:
      return

    try_job_result = yield RunTestTryJobPipeline(parameters)

    identify_culprit_input = self.CreateInputObjectInstance(
        IdentifyTestTryJobCulpritParameters,
        build_key=start_test_try_job_inputs.build_key,
        result=try_job_result)
    yield IdentifyTestTryJobCulpritPipeline(identify_culprit_input)
