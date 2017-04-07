# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipeline_wrapper import BasePipeline
from libs import analysis_status
from libs import time_util
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from waterfall import build_failure_analysis
from waterfall import suspected_cl_util


def _GetResultAnalysisStatus(analysis_result):
  """Returns the status of the analysis result.

  We can decide the status based on:
    1. whether we found any suspected CL(s).
    2. whether we have triaged the failure.
    3. whether our analysis result is the same as triaged result.
  """
  # Now we can only set the status based on if we found any suspected CL(s).
  # TODO: Add logic to decide the status after comparing with culprit CL(s).
  if not analysis_result or not analysis_result['failures']:
    return None

  for failure in analysis_result['failures']:
    if failure['suspected_cls']:
      return result_status.FOUND_UNTRIAGED

  return result_status.NOT_FOUND_UNTRIAGED


def _SaveSuspectedCLs(
    suspected_cls, master_name, builder_name, build_number, failure_type):
  """Saves suspected CLs to dataStore."""
  for suspected_cl in suspected_cls:
    suspected_cl_util.UpdateSuspectedCL(
        suspected_cl['repo_name'], suspected_cl['revision'],
        suspected_cl['commit_position'], analysis_approach_type.HEURISTIC,
        master_name, builder_name, build_number, failure_type,
        suspected_cl['failures'], suspected_cl['top_score'])


def _GetSuspectedCLsWithOnlyCLInfo(suspected_cls):
  """Removes failures and top_score from suspected_cls.

  Makes sure suspected_cls from heuristic or try_job have the same format.
  """
  simplified_suspected_cls = []
  for cl in suspected_cls:
    simplified_cl = {
        'repo_name': cl['repo_name'],
        'revision': cl['revision'],
        'commit_position': cl['commit_position'],
        'url': cl['url']
    }
    simplified_suspected_cls.append(simplified_cl)
  return simplified_suspected_cls


class IdentifyCulpritPipeline(BasePipeline):
  """A pipeline to identify culprit CLs for a build failure."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info, change_logs, deps_info, signals, build_completed):
    """Identifies culprit CL.

    Args:
      failure_info (dict): Output of pipeline DetectFirstFailurePipeline.
      change_logs (dict): Output of pipeline PullChangelogPipeline.
      signals (dict): Output of pipeline ExtractSignalPipeline.

    Returns:
      analysis_result returned by build_failure_analysis.AnalyzeBuildFailure.
    """
    master_name = failure_info['master_name']
    builder_name = failure_info['builder_name']
    build_number = failure_info['build_number']

    analysis_result, suspected_cls = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, change_logs, deps_info, signals)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.build_completed = build_completed
    analysis.result = analysis_result
    analysis.status = analysis_status.COMPLETED
    analysis.result_status = _GetResultAnalysisStatus(analysis_result)
    analysis.suspected_cls = _GetSuspectedCLsWithOnlyCLInfo(suspected_cls)
    analysis.end_time = time_util.GetUTCNow()
    analysis.put()

    # Save suspected_cls to data_store.
    _SaveSuspectedCLs(
        suspected_cls, failure_info['master_name'],
        failure_info['builder_name'], failure_info['build_number'],
        failure_info['failure_type'])
    return analysis_result
