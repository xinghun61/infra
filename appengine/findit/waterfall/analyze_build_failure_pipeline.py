# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import constants
from gae_libs import appengine_util
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from libs import time_util
from model.wf_analysis import WfAnalysis
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline
from waterfall.extract_signal_pipeline import ExtractSignalPipeline
from waterfall.flake.trigger_flake_analyses_pipeline import (
    TriggerFlakeAnalysesPipeline)
from waterfall.identify_culprit_pipeline import IdentifyCulpritPipeline
from waterfall.process_swarming_tasks_result_pipeline import (
    ProcessSwarmingTasksResultPipeline)
from waterfall.start_try_job_on_demand_pipeline import (
    StartTryJobOnDemandPipeline)
from waterfall.trigger_swarming_tasks_pipeline import (
    TriggerSwarmingTasksPipeline)


class AnalyzeBuildFailurePipeline(BasePipeline):

  def __init__(self, master_name, builder_name, build_number,
               current_failure_info, build_completed, force):
    super(AnalyzeBuildFailurePipeline,
          self).__init__(master_name, builder_name, build_number,
                         current_failure_info, build_completed, force)
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number
    self.current_failure_info = current_failure_info
    self.build_completed = build_completed
    self.force = force

  def _HandleUnexpectedAborting(self, was_aborted):
    """Handle unexpected aborting gracefully.

    Marks the WfAnalysis status as error, indicating that it was aborted.
    If one of heuristic pipelines caused the abortion, continue try job analysis
    by start a new pipeline.

    Args:
      was_aborted (bool): True if the pipeline was aborted, otherwise False.
    """
    if not was_aborted:
      return

    analysis = WfAnalysis.Get(self.master_name, self.builder_name,
                              self.build_number)
    # Heuristic analysis could have already completed, while triggering the
    # try job kept failing and lead to the abortion.
    run_try_job = False
    if not analysis.completed:
      # Heuristic analysis is aborted.
      analysis.status = analysis_status.ERROR
      analysis.result_status = None

      if analysis.failure_info:
        # We need failure_info to run try jobs,
        # while signals is optional for compile try jobs.
        run_try_job = True
    analysis.aborted = True
    analysis.put()

    # This will only run try job but not flake analysis.
    # TODO (chanli): Also run flake analysis when heuristic analysis or
    # try job analysis aborts.
    self._ContinueTryJobPipeline(run_try_job, analysis.failure_info,
                                 analysis.signals)

  def finalized(self):
    self._HandleUnexpectedAborting(self.was_aborted)

  def _ContinueTryJobPipeline(self, run_try_job, failure_info, signals):
    if not run_try_job:
      return

    try_job_pipeline = StartTryJobOnDemandPipeline(
        self.master_name, self.builder_name, self.build_number, failure_info,
        signals, None, self.build_completed, self.force)
    try_job_pipeline.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    try_job_pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    logging.info(
        'A try job pipeline for build %s, %s, %s starts after heuristic '
        'analysis was aborted.' % (self.master_name, self.builder_name,
                                   self.build_number))

  def _ResetAnalysis(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.pipeline_status_path = self.pipeline_status_path()
    analysis.status = analysis_status.RUNNING
    analysis.result_status = None
    analysis.start_time = time_util.GetUTCNow()
    analysis.version = appengine_util.GetCurrentVersion()
    analysis.end_time = None
    analysis.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, current_failure_info,
          build_completed, force):
    self._ResetAnalysis(master_name, builder_name, build_number)

    # The yield statements below return PipelineFutures, which allow subsequent
    # pipelines to refer to previous output values.
    # https://github.com/GoogleCloudPlatform/appengine-pipelines/wiki/Python

    # Heuristic Approach.
    failure_info = yield DetectFirstFailurePipeline(current_failure_info)
    signals = yield ExtractSignalPipeline(failure_info)
    heuristic_result = yield IdentifyCulpritPipeline(failure_info, signals,
                                                     build_completed)

    # Try job approach.
    with pipeline.InOrder():
      # Swarming rerun.
      # Triggers swarming tasks when first time test failure happens.
      # This pipeline will run before build completes.
      yield TriggerSwarmingTasksPipeline(master_name, builder_name,
                                         build_number, failure_info, force)

      yield ProcessSwarmingTasksResultPipeline(master_name, builder_name,
                                               build_number, failure_info,
                                               build_completed)

      # Checks if first time failures happen and starts a try job if yes.
      yield StartTryJobOnDemandPipeline(master_name, builder_name, build_number,
                                        failure_info, signals, heuristic_result,
                                        build_completed, force)

      # Trigger flake analysis on flaky tests, if any.
      yield TriggerFlakeAnalysesPipeline(master_name, builder_name,
                                         build_number)
