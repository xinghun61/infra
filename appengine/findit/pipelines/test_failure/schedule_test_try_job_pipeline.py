# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import exceptions
from gae_libs.pipelines import pipeline
from gae_libs.pipelines import SynchronousPipeline
from services.parameters import ScheduleTestTryJobParameters
from services.test_failure import test_try_job


class ScheduleTestTryJobPipeline(SynchronousPipeline):
  """A pipeline for scheduling a new try job for failed test build."""
  input_type = ScheduleTestTryJobParameters
  output_type = basestring

  def RunImpl(self, pipeline_input):
    try:
      return test_try_job.ScheduleTestTryJob(pipeline_input, self.pipeline_id)
    except exceptions.RetryException as e:
      raise pipeline.Retry('Error "%s" occurred: "%s"' % (e.error_reason,
                                                          e.error_message))
