# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs import pipelines
from gae_libs.pipeline_wrapper import pipeline_handlers
from pipelines.delay_pipeline import DelayPipeline
from waterfall.test import wf_testcase


class DelayPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testDelayPipeline(self):
    delay_pipeline = DelayPipeline(0)
    delay_pipeline.start()
    self.execute_queued_tasks()

    p = pipelines.pipeline.Pipeline.from_id(delay_pipeline.pipeline_id)
    self.assertFalse(p.was_aborted)
    self.assertEqual(0, p.outputs.default.value)
