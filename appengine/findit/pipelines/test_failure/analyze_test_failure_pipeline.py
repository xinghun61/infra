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
from gae_libs import pipelines
from gae_libs.pipelines import pipeline
from gae_libs.pipeline_wrapper import BasePipeline
from libs import analysis_status
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
from waterfall.flake.trigger_flake_analyses_pipeline import (
    TriggerFlakeAnalysesPipeline)


class AnalyzeTestFailurePipeline(BasePipeline):

  def __init__(self, master_name, builder_name, build_number,
               current_failure_info, build_completed, force):
    super(AnalyzeTestFailurePipeline,
          self).__init__(master_name, builder_name, build_number,
                         current_failure_info, build_completed, force)
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number
    self.current_failure_info = current_failure_info
    self.build_completed = build_completed
    self.force = force

  def _HandleUnexpectedAborting(self, was_aborted):
    """Handles unexpected aborting gracefully.

    Marks the WfAnalysis status as error, indicating that it was aborted.
    If one of heuristic pipelines caused the abort, continue try job analysis
    by starting a new pipeline.

    Args:
      was_aborted (bool): True if the pipeline was aborted, otherwise False.
    """
    if not was_aborted:
      return

    analysis = WfAnalysis.Get(self.master_name, self.builder_name,
                              self.build_number)
    # Heuristic analysis could have already completed, while triggering the
    # try job kept failing and lead to the abort.
    run_try_job = False
    if not analysis.completed:
      # Heuristic analysis is aborted.
      analysis.status = analysis_status.ERROR
      analysis.result_status = None

      if analysis.failure_info:
        # We need failure_info to run try jobs,
        # while signals is optional for test try jobs.
        run_try_job = True
    analysis.aborted = True
    analysis.put()

    monitoring.aborted_pipelines.increment({'type': 'test'})
    if not run_try_job:
      return

    # This will only run try job but not flake analysis.
    # TODO (chanli): Also run flake analysis when heuristic analysis or
    # try job analysis aborts.
    self._ContinueTryJobPipeline(analysis.failure_info)

  def finalized(self):
    self._HandleUnexpectedAborting(self.was_aborted)
    # Monitor completion of pipeline.
    monitoring.completed_pipelines.increment({'type': 'test'})

  def _ContinueTryJobPipeline(self, failure_info):

    heuristic_result = {'failure_info': failure_info, 'heuristic_result': None}
    start_waterfall_try_job_inputs = StartTestTryJobInputs(
        build_key=BuildKey(
            master_name=self.master_name,
            builder_name=self.builder_name,
            build_number=self.build_number),
        build_completed=self.build_completed,
        force=self.force,
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
        'analysis was aborted. Check pipeline at: %s.', self.master_name,
        self.builder_name, self.build_number, self.pipeline_status_path())

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, current_failure_info,
          build_completed, force):
    build_failure_analysis.ResetAnalysisForANewAnalysis(
        master_name, builder_name, build_number, self.pipeline_status_path(),
        appengine_util.GetCurrentVersion())

    # The yield statements below return PipelineFutures, which allow subsequent
    # pipelines to refer to previous output values.
    # https://github.com/GoogleCloudPlatform/appengine-pipelines/wiki/Python

    # Heuristic Approach.
    heuristic_params = TestHeuristicAnalysisParameters(
        failure_info=TestFailureInfo.FromSerializable(current_failure_info),
        build_completed=build_completed)
    heuristic_result = yield HeuristicAnalysisForTestPipeline(heuristic_params)

    build_key = BuildKey(
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number)

    # Try job approach.
    with pipeline.InOrder():

      run_tasks_inputs = pipelines.CreateInputObjectInstance(
          RunSwarmingTasksInput,
          build_key=build_key,
          heuristic_result=heuristic_result,
          force=force)
      # Swarming rerun.
      # Triggers swarming tasks when first time test failure happens.
      # This pipeline will run before build completes.
      yield RunSwarmingTasksPipeline(run_tasks_inputs)

      collect_task_results_inputs = pipelines.CreateInputObjectInstance(
          CollectSwarmingTaskResultsInputs,
          build_key=build_key,
          build_completed=build_completed)
      # An async pipeline that queries swarming tasks periodically until all
      # swarming tasks completes and return consistent failures.
      consistent_failures = yield CollectSwarmingTaskResultsPipeline(
          collect_task_results_inputs)

      start_waterfall_try_job_inputs = pipelines.CreateInputObjectInstance(
          StartTestTryJobInputs,
          build_key=build_key,
          build_completed=build_completed,
          force=force,
          heuristic_result=heuristic_result,
          consistent_failures=consistent_failures)
      yield StartTestTryJobPipeline(start_waterfall_try_job_inputs)

      if not force:
        # Report event to BQ.
        report_event_input = pipelines.CreateInputObjectInstance(
            report_event_pipeline.ReportEventInput,
            analysis_urlsafe_key=WfAnalysis.Get(master_name, builder_name,
                                                build_number).key.urlsafe())
        yield report_event_pipeline.ReportAnalysisEventPipeline(
            report_event_input)

      # Trigger flake analysis on flaky tests, if any.
      yield TriggerFlakeAnalysesPipeline(master_name, builder_name,
                                         build_number)
