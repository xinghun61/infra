# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers

from pipelines.delay_pipeline import DelayPipeline
from waterfall.test import wf_testcase


class DelayPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testDelayPipeline(self):
    delay_pipeline = DelayPipeline(0)
    delay_pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()