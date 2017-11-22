# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from gae_libs.pipeline_wrapper import BasePipeline
from libs import time_util

from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from waterfall import waterfall_config
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

    flake_settings = waterfall_config.GetCheckFlakeSettings()
    throttled = flake_settings.get('throttle_flake_analyses', True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)

    if not analysis or not analysis.failure_result_map:  # pragma: no cover
      return

    for step in analysis.failure_result_map.iterkeys():
      task = WfSwarmingTask.Get(master_name, builder_name, build_number, step)

      if not task:  # pragma: no cover
        continue

      flaky_tests = task.classified_tests.get('flaky_tests', [])

      if not flaky_tests:  # pragma: no cover
        continue

      logging.info('%s/%s/%s/%s has %s flaky tests.', master_name, builder_name,
                   build_number, step, len(flaky_tests))

      for test_name in flaky_tests:
        request = FlakeAnalysisRequest.Create(test_name, False, None)
        request.AddBuildStep(master_name, builder_name, build_number, step,
                             time_util.GetUTCNow())
        scheduled = flake_analysis_service.ScheduleAnalysisForFlake(
            request, 'findit-for-me@appspot.gserviceaccount.com', False,
            triggering_sources.FINDIT_PIPELINE)
        if scheduled:
          logging.info('A flake analysis has been triggered for %s/%s', step,
                       test_name)
          if throttled:
            logging.info('Throttling is enabled, skipping %d tests.',
                         len(flaky_tests) - 1)
            break  # If we're thottled, stop after the first.
