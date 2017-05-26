# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import BasePipeline
from model import result_status
from model.wf_analysis import WfAnalysis
from waterfall import swarming_util


def _GetFlakyTests(task_results):
  flaky_failures = defaultdict(list)
  for step, step_task_results in task_results.iteritems():
    flaky_tests = step_task_results
    if flaky_tests:
      flaky_failures[step].extend(flaky_tests)
  return flaky_failures


@ndb.transactional
def _UpdateAnalysisWithFlakeInfo(
    master_name, builder_name, build_number, flaky_tests):

  if not flaky_tests:
    return False

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis or not analysis.result:
    return False

  all_flaked = swarming_util.UpdateAnalysisResult(analysis.result, flaky_tests)
  if all_flaked:
    analysis.result_status = result_status.FLAKY
  analysis.put()
  return True


class UpdateAnalysisWithFlakeInfoPipeline(BasePipeline):
  """A pipeline to update analysis with flake info."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, *task_results):
    """
    Args:
    master_name (str): The master name.
    builder_name (str): The builder name.
    build_number (str): The build number.
    flaky_tests (list): A list of results from swarming tasks.
    """
    flaky_tests = _GetFlakyTests(dict(task_results))
    _UpdateAnalysisWithFlakeInfo(
        master_name, builder_name, build_number, flaky_tests)
