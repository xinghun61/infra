# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging

from gae_libs.pipelines import GeneratorPipeline
from libs import time_util
from model.flake.analysis import triggering_sources
from model.flake.analysis.flake_analysis_request import FlakeAnalysisRequest
from model.wf_analysis import WfAnalysis
from services import flake_util
from services import monitoring
from services import step_util
from services.parameters import BuildKey
from waterfall import waterfall_config
from waterfall.flake import flake_analysis_service

# TODO(crbug.com/905458): Dynamically capture/store luci project.
_LUCI_PROJECT = 'chromium'


# TODO(crbug.com/904048): Route through Flake Detection instead.
class TriggerFlakeAnalysesPipeline(GeneratorPipeline):
  """A pipeline that automatically triggers flake analyses."""
  input_type = BuildKey

  def RunImpl(self, build_key):
    """Triggers flake analyses for flaky tests found by CI failure analysis."""
    master_name, builder_name, build_number = build_key.GetParts()
    flake_settings = waterfall_config.GetCheckFlakeSettings()
    throttled = flake_settings.get('throttle_flake_analyses', True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)

    if not analysis or not analysis.flaky_tests:
      return

    analysis_counts = defaultdict(lambda: defaultdict(int))
    for step, flaky_tests in analysis.flaky_tests.iteritems():
      logging.info('%s/%s/%s/%s has %s flaky tests.', master_name, builder_name,
                   build_number, step, len(flaky_tests))

      for test_name in flaky_tests:
        # TODO(crbug.com/904050): Deprecate FlakeAnalysisRequest in favor of
        # Flake.
        flake = flake_util.GetFlake(_LUCI_PROJECT, step, test_name, master_name,
                                    builder_name, build_number)
        request = FlakeAnalysisRequest.Create(test_name, False, None)
        request.AddBuildStep(master_name, builder_name, build_number, step,
                             time_util.GetUTCNow())
        request.flake_key = flake.key
        scheduled = flake_analysis_service.ScheduleAnalysisForFlake(
            request, 'findit-for-me@appspot.gserviceaccount.com', False,
            triggering_sources.FINDIT_PIPELINE)
        if scheduled:  # pragma: no branch
          analysis_counts[step]['analyzed'] += 1
          logging.info('A flake analysis has been triggered for %s/%s', step,
                       test_name)
          if throttled and len(flaky_tests) > 1:
            logging.info('Throttling is enabled, skipping %d tests.',
                         len(flaky_tests) - 1)
            analysis_counts[step]['throttled'] = len(flaky_tests) - 1
            break  # If we're throttled, stop after the first.
      else:
        analysis_counts[step]['error'] += 1

    for step, step_counts in analysis_counts.iteritems():
      # Collects metrics.
      step_metadata = step_util.LegacyGetStepMetadata(master_name, builder_name,
                                                      build_number, step)
      canonical_step_name = step_metadata.get(
          'canonical_step_name') or 'Unknown'
      isolate_target_name = step_metadata.get(
          'isolate_target_name') or 'Unknown'

      for operation, count in step_counts.iteritems():
        monitoring.OnFlakeIdentified(canonical_step_name, isolate_target_name,
                                     operation, count)
