# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipeline_wrapper import BasePipeline
from model.wf_analysis import WfAnalysis
from model.wf_try_job_data import WfTryJobData
from pipelines.compile_failure import (
    revert_and_notify_compile_culprit_pipeline as revert_pipeline)
from services import build_failure_analysis
from services import try_job
from services.compile_failure import compile_try_job


class IdentifyCompileTryJobCulpritPipeline(BasePipeline):
  """A pipeline to identify culprit CL info based on try job compile results."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, try_job_id, result):
    """Identifies the information for failed revisions.

    Please refer to try_job_result_format.md for format check.
    """
    culprits = None
    flaky_compile = False
    if try_job_id and result and result.get('report'):
      failed_revision = compile_try_job.GetFailedRevisionFromCompileResult(
          result)
      failed_revisions = [failed_revision] if failed_revision else []
      culprits = try_job.GetCulpritInfo(failed_revisions)

      # In theory there are 2 cases where compile failure could be flaky:
      # 1. All revisions passed in the try job (try job will not run at good
      # revision in this case),
      # 2. The compile even failed at good revision.
      # We cannot guarantee in the first case the compile failure is flaky
      # because it's also possible the difference between buildbot and trybot
      # causes this.
      # So currently we'll only consider the second case.
      if not culprits and compile_try_job.CompileFailureIsFlaky(result):
        flaky_compile = True

      if culprits:
        result['culprit'] = {'compile': culprits[failed_revision]}
        try_job_data = WfTryJobData.Get(try_job_id)
        try_job_data.culprits = {'compile': failed_revision}
        try_job_data.put()

    # Store try-job results.
    compile_try_job.UpdateTryJobResult(master_name, builder_name, build_number,
                                       result, try_job_id, culprits)

    # Saves cls found by heuristic approach to determine a culprit is found
    # by both heuristic and try job when sending notifications.
    # This part must be before UpdateWfAnalysisWithTryJobResult().
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    heuristic_cls = build_failure_analysis.GetHeuristicSuspectedCLs(analysis)

    # Add try-job results to WfAnalysis.
    compile_try_job.UpdateWfAnalysisWithTryJobResult(master_name, builder_name,
                                                     build_number, result,
                                                     culprits, flaky_compile)

    # TODO (chanli): Update suspected_cl for builds in the same group with
    # current build.
    # Updates suspected_cl.
    compile_try_job.UpdateSuspectedCLs(master_name, builder_name, build_number,
                                       culprits)

    if not culprits:
      return

    yield revert_pipeline.RevertAndNotifyCompileCulpritPipeline(
        master_name, builder_name, build_number, culprits, heuristic_cls)
