# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import exceptions

from gae_libs.pipelines import pipeline
from gae_libs.pipelines import SynchronousPipeline

from services.flake_failure import flake_try_job
from services.parameters import RunFlakeTryJobParameters


class RunFlakeTryJobPipeline(SynchronousPipeline):
  """A pipeline for running a new try job to compile and isolate."""
  # TODO(crbug.com/787618): Make pipeline asynchronous and add callbacks.
  input_type = RunFlakeTryJobParameters
  output_type = basestring

  def RunImpl(self, pipeline_input):
    try:
      return flake_try_job.ScheduleFlakeTryJob(pipeline_input, self.pipeline_id)
    except exceptions.RetryException as e:
      raise pipeline.Retry('Error "%s" occurred: "%s"' % (e.error_reason,
                                                          e.error_message))
