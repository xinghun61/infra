# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import constants
from common import monitoring
from dto.start_waterfall_try_job_inputs import StartCompileTryJobInput
from gae_libs import appengine_util
from gae_libs import pipelines
from gae_libs.pipelines import GeneratorPipeline
from libs.structured_object import StructuredObject
from model import analysis_approach_type
from model.wf_analysis import WfAnalysis
from pipelines import report_event_pipeline
from pipelines.compile_failure.heuristic_analysis_for_compile_pipeline import (
    HeuristicAnalysisForCompilePipeline)
from pipelines.compile_failure.start_compile_try_job_pipeline import (
    StartCompileTryJobPipeline)
from services.compile_failure import compile_failure_analysis
from services import build_failure_analysis
from services.parameters import BuildKey
from services.parameters import CompileFailureInfo
from services.parameters import CompileHeuristicAnalysisOutput
from services.parameters import CompileHeuristicAnalysisParameters


class AnalyzeCompileFailureInput(StructuredObject):
  build_key = BuildKey
  current_failure_info = CompileFailureInfo
  build_completed = bool
  force = bool


class AnalyzeCompileFailurePipeline(GeneratorPipeline):
  input_type = AnalyzeCompileFailureInput

  def OnFinalized(self, _arg):
    monitoring.completed_pipelines.increment({'type': 'compile'})

  def OnAbort(self, pipeline_input):
    """Handles unexpected aborting gracefully.

    Marks the WfAnalysis status as error, indicating that it was aborted.
    If one of heuristic pipelines caused the abort, continue try job analysis
    by starting a new pipeline.
    """
    analysis, run_try_job, heuristic_aborted = (
        build_failure_analysis.UpdateAbortedAnalysis(pipeline_input))

    # Records that heuristic analysis ends in error.
    if heuristic_aborted:
      master_name, builder_name, _ = pipeline_input.build_key.GetParts()
      compile_failure_analysis.RecordCompileFailureAnalysisStateChange(
          master_name, builder_name, analysis.status,
          analysis_approach_type.HEURISTIC)
    monitoring.aborted_pipelines.increment({'type': 'compile'})

    if not run_try_job:
      return

    self._ContinueTryJobPipeline(pipeline_input, analysis.failure_info,
                                 analysis.signals)

  def _ContinueTryJobPipeline(self, pipeline_input, failure_info, signals):
    heuristic_result = {
        'failure_info': failure_info,
        'signals': signals,
        'heuristic_result': None
    }
    start_compile_try_job_input = StartCompileTryJobInput(
        build_key=pipeline_input.build_key,
        heuristic_result=CompileHeuristicAnalysisOutput.FromSerializable(
            heuristic_result),
        build_completed=pipeline_input.build_completed,
        force=pipeline_input.force)
    try_job_pipeline = StartCompileTryJobPipeline(start_compile_try_job_input)
    try_job_pipeline.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    try_job_pipeline.start(queue_name=constants.WATERFALL_ANALYSIS_QUEUE)

    master_name, builder_name, build_number = (
        pipeline_input.build_key.GetParts())
    logging.info(
        'A try job pipeline for build %s, %s, %s starts after heuristic '
        'analysis was aborted. Check pipeline at: %s.', master_name,
        builder_name, build_number, self.pipeline_status_path)

  def RunImpl(self, pipeline_input):
    master_name, builder_name, build_number = (
        pipeline_input.build_key.GetParts())

    build_failure_analysis.ResetAnalysisForANewAnalysis(
        master_name,
        builder_name,
        build_number,
        build_completed=pipeline_input.build_completed,
        pipeline_status_path=self.pipeline_status_path,
        current_version=appengine_util.GetCurrentVersion())

    # TODO(crbug/869684): Use a gauge metric to track intermittent statuses.

    # The yield statements below return PipelineFutures, which allow subsequent
    # pipelines to refer to previous output values.
    # https://github.com/GoogleCloudPlatform/appengine-pipelines/wiki/Python

    # Heuristic Approach.
    heuristic_params = CompileHeuristicAnalysisParameters(
        failure_info=pipeline_input.current_failure_info,
        build_completed=pipeline_input.build_completed)
    heuristic_result = yield HeuristicAnalysisForCompilePipeline(
        heuristic_params)

    # Try job approach.
    # Checks if first time failures happen and starts a try job if yes.
    with pipelines.pipeline.InOrder():
      start_compile_try_job_input = self.CreateInputObjectInstance(
          StartCompileTryJobInput,
          build_key=BuildKey(
              master_name=master_name,
              builder_name=builder_name,
              build_number=build_number),
          heuristic_result=heuristic_result,
          build_completed=pipeline_input.build_completed,
          force=pipeline_input.force)
      yield StartCompileTryJobPipeline(start_compile_try_job_input)
      # Report event to BQ.
      report_event_input = self.CreateInputObjectInstance(
          report_event_pipeline.ReportEventInput,
          analysis_urlsafe_key=WfAnalysis.Get(master_name, builder_name,
                                              build_number).key.urlsafe())
      if not pipeline_input.force:
        yield report_event_pipeline.ReportAnalysisEventPipeline(
            report_event_input)
