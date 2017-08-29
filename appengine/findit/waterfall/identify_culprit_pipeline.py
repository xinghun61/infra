# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipeline_wrapper import BasePipeline
from waterfall import build_failure_analysis


class IdentifyCulpritPipeline(BasePipeline):
  """A pipeline to identify culprit CLs for a build failure."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info, signals, build_completed):
    """Identifies culprit CL.

    Args:
      failure_info (dict): Output of pipeline DetectFirstFailurePipeline.
      signals (dict): Output of pipeline ExtractSignalPipeline.

    Returns:
      analysis_result returned by build_failure_analysis.AnalyzeBuildFailure.
    """
    master_name = failure_info['master_name']
    builder_name = failure_info['builder_name']
    build_number = failure_info['build_number']

    change_logs = build_failure_analysis.PullChangeLogs(failure_info)
    deps_info = build_failure_analysis.ExtractDepsInfo(failure_info,
                                                       change_logs)

    analysis_result, suspected_cls = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, change_logs, deps_info, signals)

    # Save results and other info to analysis.
    build_failure_analysis.SaveAnalysisAfterHeuristicAnalysisCompletes(
        master_name, builder_name, build_number, build_completed,
        analysis_result, suspected_cls)

    # Save suspected_cls to data_store.
    build_failure_analysis.SaveSuspectedCLs(
        suspected_cls, failure_info['master_name'],
        failure_info['builder_name'], failure_info['build_number'],
        failure_info['failure_type'])
    return analysis_result
