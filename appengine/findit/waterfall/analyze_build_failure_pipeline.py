# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs import appengine_util
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import time_util
from model import analysis_status
from model.wf_analysis import WfAnalysis
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline
from waterfall.extract_deps_info_pipeline import ExtractDEPSInfoPipeline
from waterfall.extract_signal_pipeline import ExtractSignalPipeline
from waterfall.flake.trigger_flake_analyses_pipeline import (
    TriggerFlakeAnalysesPipeline)
from waterfall.identify_culprit_pipeline import IdentifyCulpritPipeline
from waterfall.pull_changelog_pipeline import PullChangelogPipeline
from waterfall.start_try_job_on_demand_pipeline import (
    StartTryJobOnDemandPipeline)
from waterfall.trigger_swarming_tasks_pipeline import (
    TriggerSwarmingTasksPipeline)


class AnalyzeBuildFailurePipeline(BasePipeline):

  def __init__(self, master_name, builder_name, build_number, build_completed,
               force_rerun_try_job):
    super(AnalyzeBuildFailurePipeline, self).__init__(
        master_name, builder_name, build_number, build_completed,
        force_rerun_try_job)
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number

  def _LogUnexpectedAborting(self, was_aborted):
    """Marks the WfAnalysis status as error, indicating that it was aborted.

    Args:
      was_aborted (bool): True if the pipeline was aborted, otherwise False.
    """
    if not was_aborted:
      return

    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number)
    # Heuristic analysis could have already completed, while triggering the
    # try job kept failing and lead to the abortion.
    if not analysis.completed:
      analysis.status = analysis_status.ERROR
      analysis.result_status = None
    analysis.aborted = True
    analysis.put()

  def finalized(self):
    self._LogUnexpectedAborting(self.was_aborted)

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
  def run(self, master_name, builder_name, build_number, build_completed,
          force_rerun_try_job):
    self._ResetAnalysis(master_name, builder_name, build_number)

    # The yield statements below return PipelineFutures, which allow subsequent
    # pipelines to refer to previous output values.
    # https://github.com/GoogleCloudPlatform/appengine-pipelines/wiki/Python

    # Heuristic Approach.
    failure_info = yield DetectFirstFailurePipeline(
        master_name, builder_name, build_number)
    change_logs = yield PullChangelogPipeline(failure_info)
    deps_info = yield ExtractDEPSInfoPipeline(failure_info, change_logs)
    signals = yield ExtractSignalPipeline(failure_info)
    heuristic_result = yield IdentifyCulpritPipeline(
        failure_info, change_logs, deps_info, signals, build_completed)

    # Try job approach.
    with pipeline.InOrder():
      # Swarming rerun.
      # Triggers swarming tasks when first time test failure happens.
      # This pipeline will run before build completes.
      yield TriggerSwarmingTasksPipeline(
          master_name, builder_name, build_number, failure_info)

      # Checks if first time failures happen and starts a try job if yes.
      yield StartTryJobOnDemandPipeline(
          master_name, builder_name, build_number, failure_info,
          signals, heuristic_result, build_completed, force_rerun_try_job)

      # Trigger flake analysis on flaky tests, if any.
      yield TriggerFlakeAnalysesPipeline(
          master_name, builder_name, build_number)
