# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import exceptions
from gae_libs.pipelines import pipeline
from gae_libs.pipelines import SynchronousPipeline
from services.compile_failure import compile_try_job
from services.parameters import ScheduleCompileTryJobParameters


class ScheduleCompileTryJobPipeline(SynchronousPipeline):
  """A pipeline for scheduling a new try job for failed compile build."""
  input_type = ScheduleCompileTryJobParameters
  output_type = basestring

  def RunImpl(self, pipeline_input):
    try:
      return compile_try_job.ScheduleCompileTryJob(pipeline_input,
                                                   self.pipeline_id)
    except exceptions.RetryException as e:
      raise pipeline.Retry('Error "%s" occurred: "%s"' % (e.error_reason,
                                                          e.error_message))
