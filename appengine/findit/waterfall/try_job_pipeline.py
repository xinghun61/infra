# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from pipeline_wrapper import BasePipeline
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from waterfall.identify_try_job_culprit_pipeline import (
    IdentifyTryJobCulpritPipeline)
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.schedule_try_job_pipeline import ScheduleTryJobPipeline


class TryJobPipeline(BasePipeline):
  """Root pipeline to start a tryjob on current build."""

  def __init__(self, master_name, builder_name, build_number,
      good_revision, bad_revision):
    super(TryJobPipeline, self).__init__(
        master_name, builder_name, build_number, good_revision, bad_revision)
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number
    self.good_revision = good_revision
    self.bad_revision = bad_revision

  def _LogUnexpectedAbort(self, was_aborted):
    """Marks the WfTryJob status as error, indicating that it was aborted.

    Args:
      was_aborted (bool): True if the pipeline was aborted due to some error
      or exception, otherwise False.
    """
    if was_aborted:
      try_job_result = WfTryJob.Get(
          self.master_name, self.builder_name, self.build_number)
      if try_job_result:  # In case the result is deleted manually.
        try_job_result.status = wf_analysis_status.ERROR
        try_job_result.put()

  def finalized(self):
    """Finalizes this Pipeline after execution."""
    self._LogUnexpectedAbort(self.was_aborted)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number,
      good_revision, bad_revision):
    try_job_id = yield ScheduleTryJobPipeline(
        master_name, builder_name, build_number, good_revision, bad_revision)
    compile_result = yield MonitorTryJobPipeline(
        master_name, builder_name, build_number, try_job_id)
    yield IdentifyTryJobCulpritPipeline(
        master_name, builder_name, build_number, try_job_id, compile_result)
