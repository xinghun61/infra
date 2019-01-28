# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import constants
from common import monitoring
from dto.collect_swarming_task_results_inputs import (
    CollectSwarmingTaskResultsInputs)
from dto.collect_swarming_task_results_outputs import (
    CollectSwarmingTaskResultsOutputs)
from dto.run_swarming_tasks_input import RunSwarmingTasksInput
from dto.start_waterfall_try_job_inputs import StartTestTryJobInputs
from gae_libs import appengine_util
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import pipeline
from libs.structured_object import StructuredObject
from model import analysis_approach_type
from model.wf_analysis import WfAnalysis
from pipelines import report_event_pipeline
from pipelines.test_failure.collect_swarming_task_results_pipeline import (
    CollectSwarmingTaskResultsPipeline)
from pipelines.test_failure.heuristic_analysis_for_test_pipeline import (
    HeuristicAnalysisForTestPipeline)
from pipelines.test_failure.run_swarming_tasks_pipeline import (
    RunSwarmingTasksPipeline)
from pipelines.test_failure.start_test_try_job_pipeline import (
    StartTestTryJobPipeline)
from services import build_failure_analysis
from services.parameters import BuildKey
from services.parameters import TestFailureInfo
from services.parameters import TestHeuristicAnalysisOutput
from services.parameters import TestHeuristicAnalysisParameters
from services.test_failure import test_failure_analysis


class AnalyzeTestFailureInput(StructuredObject):
  # Key to the build, includes master_name, builder_name and build_number.
  build_key = BuildKey
  # Result of ci_failure.GetBuildFailureInfo.
  # Initial failure info for the build that is being analyzed.
  current_failure_info = TestFailureInfo
  build_completed = bool
  force = bool


class AnalyzeTestFailurePipeline(GeneratorPipeline):
  input_type = AnalyzeTestFailureInput

  def OnFinalized(self, _pipeline_input):
    monitoring.completed_pipelines.increment({'type': 'test'})

  def OnAbort(self, pipeline_input):
    """Handles unexpected aborting gracefully.

    Marks the WfAnalysis status as error, indicating that it was aborted.
    If one of heuristic pipelines caused the abort, continue try job analysis
    by starting a new pipeline.
    """
    analysis, run_try_job, heuristic_aborted = (
        build_failure_analysis.UpdateAbortedAnalysis(pipeline_input))

    if (heuristic_aborted and analysis.failure_info and
        pipeline_input.build_completed):
      # Records that heuristic analysis ends in error.
      master_name, builder_name, _ = (pipeline_input.build_key.GetParts())
      test_failure_analysis.RecordTestFailureAnalysisStateChange(
          master_name, builder_name, analysis.status,
          analysis_approach_type.HEURISTIC)
    monitoring.aborted_pipelines.increment({'type': 'test'})

    if not run_try_job:
      return

    # This will only run try job but not flake analysis.
    # TODO (chanli): Also run flake analysis when heuristic analysis or
    # try job analysis aborts.
    self._ContinueTryJobPipeline(pipeline_input, analysis.failure_info)

  def _ContinueTryJobPipeline(self, pipeline_input, failure_info):
    master_name, builder_name, build_number = (
        pipeline_input.build_key.GetParts())
    heuristic_result = {'failure_info': failure_info, 'heuristic_result': None}
    start_waterfall_try_job_inputs = StartTestTryJobInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=pipeline_input.build_completed,
        force=pipeline_input.force,
        heuristic_result=TestHeuristicAnalysisOutput.FromSerializable(
            heuristic_result),
        consistent_failures=CollectSwarmingTaskResultsOutputs.FromSerializable(
            {}))
    try_job_pipeline = StartTestTryJobPipeline(start_waterfall_try_job_inputs)
    try_job_pipeline.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    try_job_pipeline.start(queue_name=constants.WATERFALL_ANALYSIS_QUEUE)
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
    heuristic_params = TestHeuristicAnalysisParameters(
        failure_info=pipeline_input.current_failure_info,
        build_completed=pipeline_input.build_completed)
    heuristic_result = yield HeuristicAnalysisForTestPipeline(heuristic_params)

    # Try job approach.
    with pipeline.InOrder():
      run_tasks_inputs = self.CreateInputObjectInstance(
          RunSwarmingTasksInput,
          build_key=pipeline_input.build_key,
          heuristic_result=heuristic_result,
          force=pipeline_input.force)
      # Swarming rerun.
      # Triggers swarming tasks when first time test failure happens.
      # This pipeline will run before build completes.
      yield RunSwarmingTasksPipeline(run_tasks_inputs)

      collect_task_results_inputs = self.CreateInputObjectInstance(
          CollectSwarmingTaskResultsInputs,
          build_key=pipeline_input.build_key,
          build_completed=pipeline_input.build_completed)
      # An async pipeline that queries swarming tasks periodically until all
      # swarming tasks completes and return consistent failures.
      consistent_failures = yield CollectSwarmingTaskResultsPipeline(
          collect_task_results_inputs)

      start_waterfall_try_job_inputs = self.CreateInputObjectInstance(
          StartTestTryJobInputs,
          build_key=pipeline_input.build_key,
          build_completed=pipeline_input.build_completed,
          force=pipeline_input.force,
          heuristic_result=heuristic_result,
          consistent_failures=consistent_failures)
      yield StartTestTryJobPipeline(start_waterfall_try_job_inputs)

      if not pipeline_input.force:
        # Report event to BQ.
        report_event_input = self.CreateInputObjectInstance(
            report_event_pipeline.ReportEventInput,
            analysis_urlsafe_key=WfAnalysis.Get(master_name, builder_name,
                                                build_number).key.urlsafe())
        yield report_event_pipeline.ReportAnalysisEventPipeline(
            report_event_input)
