# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from google.appengine.api import modules

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall.base_pipeline import BasePipeline
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline
from waterfall.extract_deps_info_pipeline import ExtractDEPSInfoPipeline
from waterfall.extract_signal_pipeline import ExtractSignalPipeline
from waterfall.identify_culprit_pipeline import IdentifyCulpritPipeline
from waterfall.pull_changelog_pipeline import PullChangelogPipeline


class AnalyzeBuildFailurePipeline(BasePipeline):

  def __init__(self, master_name, builder_name, build_number):
    super(AnalyzeBuildFailurePipeline, self).__init__(
        master_name, builder_name, build_number)
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
        analysis.status = wf_analysis_status.ERROR
        analysis.result_status = None
        analysis.put()

  def finalized(self):
    self._LogUnexpectedAborting(self.was_aborted)

  def pipeline_status_path(self):
    """Returns an absolute path to look up the status of the pipeline."""
    return '/_ah/pipeline/status?root=%s&auto=false' % self.root_pipeline_id

  def _ResetAnalysis(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.pipeline_status_path = self.pipeline_status_path()
    analysis.status = wf_analysis_status.ANALYZING
    analysis.result_status = None
    analysis.start_time = datetime.utcnow()
    analysis.version = modules.get_current_version_name()
    analysis.end_time = None
    analysis.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number):
    self._ResetAnalysis(master_name, builder_name, build_number)

    # The yield statements below return PipelineFutures, which allow subsequent
    # pipelines to refer to previous output values.
    # https://github.com/GoogleCloudPlatform/appengine-pipelines/wiki/Python
    failure_info = yield DetectFirstFailurePipeline(
        master_name, builder_name, build_number)
    change_logs = yield PullChangelogPipeline(failure_info)
    deps_info = yield ExtractDEPSInfoPipeline(failure_info, change_logs)
    signals = yield ExtractSignalPipeline(failure_info)
    yield IdentifyCulpritPipeline(
        failure_info, change_logs, deps_info, signals)
