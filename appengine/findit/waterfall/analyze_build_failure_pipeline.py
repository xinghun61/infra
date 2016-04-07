# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from common import appengine_util
from model.wf_analysis import WfAnalysis
from model import analysis_status
from pipeline_wrapper import BasePipeline
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline
from waterfall.extract_deps_info_pipeline import ExtractDEPSInfoPipeline
from waterfall.extract_signal_pipeline import ExtractSignalPipeline
from waterfall.identify_culprit_pipeline import IdentifyCulpritPipeline
from waterfall.pull_changelog_pipeline import PullChangelogPipeline


class AnalyzeBuildFailurePipeline(BasePipeline):

  def __init__(self, master_name, builder_name, build_number, build_completed):
    super(AnalyzeBuildFailurePipeline, self).__init__(
        master_name, builder_name, build_number, build_completed)
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number

  def _LogUnexpectedAborting(self, was_aborted):
    """Marks the WfAnalysis status as error, indicating that it was aborted.

    Args:
      was_aborted (bool): True if the pipeline was aborted, otherwise False.
    """
    if was_aborted:
      analysis = WfAnalysis.Get(
          self.master_name, self.builder_name, self.build_number)
      if analysis:  # In case the analysis is deleted manually.
        analysis.status = analysis_status.ERROR
        analysis.result_status = None
        analysis.put()

  def finalized(self):
    self._LogUnexpectedAborting(self.was_aborted)

  def _ResetAnalysis(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.pipeline_status_path = self.pipeline_status_path()
    analysis.status = analysis_status.RUNNING
    analysis.result_status = None
    analysis.start_time = datetime.utcnow()
    analysis.version = appengine_util.GetCurrentVersion()
    analysis.end_time = None
    analysis.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, build_completed):
    self._ResetAnalysis(master_name, builder_name, build_number)

    # The yield statements below return PipelineFutures, which allow subsequent
    # pipelines to refer to previous output values.
    # https://github.com/GoogleCloudPlatform/appengine-pipelines/wiki/Python
    failure_info = yield DetectFirstFailurePipeline(
        master_name, builder_name, build_number)
    change_logs = yield PullChangelogPipeline(failure_info)
    deps_info = yield ExtractDEPSInfoPipeline(failure_info, change_logs)
    signals = yield ExtractSignalPipeline(failure_info, build_completed)
    yield IdentifyCulpritPipeline(
        failure_info, change_logs, deps_info, signals, build_completed)
