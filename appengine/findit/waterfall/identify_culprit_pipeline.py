# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall import build_failure_analysis
from waterfall.base_pipeline import BasePipeline


def _GetSuspectedCLs(analysis_result):
  """Returns the suspected CLs we found in analysis."""
  suspected_cls = []
  for failure in analysis_result['failures']:
    for suspected_cl in failure['suspected_cls']:
      cl_info = {
          'repo_name': suspected_cl['repo_name'],
          'revision': suspected_cl['revision'],
          'commit_position': suspected_cl['commit_position'],
          'url': suspected_cl['url']
      }
      if cl_info not in suspected_cls:
        suspected_cls.append(cl_info)
  return suspected_cls


class IdentifyCulpritPipeline(BasePipeline):
  """A pipeline to identify culprit CLs for a build failure."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info, change_logs, signals):
    """
    Args:
      failure_info (dict): Output of pipeline DetectFirstFailurePipeline.
      change_logs (dict): Output of pipeline PullChangelogPipeline.
      signals (dict): Output of pipeline ExtractSignalPipeline.

    Returns:
      The same dict as the returned value of function
      build_failure_analysis.AnalyzeBuildFailure.
    """
    master_name = failure_info['master_name']
    builder_name = failure_info['builder_name']
    build_number = failure_info['build_number']

    analysis_result = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, change_logs, signals)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.result = analysis_result
    analysis.status = wf_analysis_status.ANALYZED
    analysis.suspected_cls = _GetSuspectedCLs(analysis_result)
    analysis.put()

    return analysis_result
