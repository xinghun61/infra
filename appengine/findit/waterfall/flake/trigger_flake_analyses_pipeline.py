# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from gae_libs.pipeline_wrapper import BasePipeline
from libs import time_util
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from waterfall.flake import flake_analysis_service
from waterfall.flake import triggering_sources


class TriggerFlakeAnalysesPipeline(BasePipeline):
  """A pipeline that automatically triggers flake analyses."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number):
    """Triggers flake analyses for flaky tests found by build failure analysis.

    Args:
      master_name (str): The master name.
      builder_name (str): The builder name.
      build_number (str): The build number.
    """

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)

    if not analysis:  # pragma: no cover
      return

    for step in analysis.failure_result_map.iterkeys():
      task = WfSwarmingTask.Get(
          master_name, builder_name, build_number, step)

      if not task:  # pragma: no cover
        continue

      flaky_tests = task.classified_tests.get('flaky_tests', [])

      if not flaky_tests:  # pragma: no cover
        continue

      # Trigger a master flake analysis on each detected flaky test.
      # TODO lijeffrey): rerun all tests once typical load is determined to be
      # within reasonable limits. For experimentation with automatic flakiness
      # checking, only run 1 test per anaysis to avoid excessive load on the
      # swarming server in case there are too many flaky tests per analysis for
      # now.
      test_name = flaky_tests[0]
      request = FlakeAnalysisRequest.Create(test_name, False, None)
      request.AddBuildStep(
          master_name, builder_name, build_number, step,
          time_util.GetUTCNow())
      scheduled = flake_analysis_service.ScheduleAnalysisForFlake(
          request, 'findit-for-me@appspot.gserviceaccount.com', False,
          triggering_sources.FINDIT_PIPELINE)

      if scheduled:  # pragma: no branch
        logging.info('%s/%s/%s has %s flaky tests.',
                     master_name, builder_name, build_number, len(flaky_tests))
        logging.info('A flake analysis has been triggered for %s', test_name)
