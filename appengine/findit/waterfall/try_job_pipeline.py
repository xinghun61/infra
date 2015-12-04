# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from pipeline_wrapper import BasePipeline
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.schedule_try_job_pipeline import ScheduleTryJobPipeline


class TryJobPipeline(BasePipeline):
  """Root pipeline to start a tryjob on current build."""
  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, revisions):
    tryjob_ids = yield ScheduleTryJobPipeline(
        master_name, builder_name, revisions)
    yield MonitorTryJobPipeline(
        master_name, builder_name, build_number, tryjob_ids)
