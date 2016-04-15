# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.pipeline_wrapper import BasePipeline
from common.waterfall import failure_type
from model.wf_analysis import WfAnalysis
from waterfall import try_job_util


class StartTryJobOnDemandPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info, signals, build_completed, heuristic_result):
    """Starts a try job if one is needed for the given failure."""
    if not build_completed:  # Only start try-jobs for completed builds.
      return False

    failure_result_map = try_job_util.ScheduleTryJobIfNeeded(
        failure_info, signals=signals, heuristic_result=heuristic_result)

    # Save reference to the try-jobs if any was scheduled.
    master_name = failure_info['master_name']
    builder_name = failure_info['builder_name']
    build_number = failure_info['build_number']
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.failure_result_map = failure_result_map
    analysis.put()
    return True
