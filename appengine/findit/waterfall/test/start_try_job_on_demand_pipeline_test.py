# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common.pipeline_wrapper import pipeline_handlers
from model.wf_analysis import WfAnalysis
from waterfall import try_job_util
from waterfall.start_try_job_on_demand_pipeline import (
    StartTryJobOnDemandPipeline)


class StartTryJobOnDemandPipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  def _MockTryJobScheduling(self, requests):
    def Mocked_ScheduleTryJobIfNeeded(*args, **kwargs):
      requests.append((args, kwargs))
      return {'compile': 'try-job-key'}
    self.mock(
        try_job_util, 'ScheduleTryJobIfNeeded', Mocked_ScheduleTryJobIfNeeded)

  def testNotScheduleTryJobIfBuildNotCompleted(self):
    requests = []
    self._MockTryJobScheduling(requests)
    pipeline = StartTryJobOnDemandPipeline()
    self.assertFalse(pipeline.run(None, None, False, False, None))
    self.assertEqual(0, len(requests))

  def testTryJobScheduled(self):
    master_name, builder_name, build_number = 'm', 'b', 123
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
    }

    requests = []
    self._MockTryJobScheduling(requests)

    pipeline = StartTryJobOnDemandPipeline()
    self.assertTrue(pipeline.run(failure_info, None, True, False, None))
    self.assertEqual(1, len(requests))
    self.assertEqual(
        {'compile': 'try-job-key'},
        WfAnalysis.Get(
            master_name, builder_name, build_number).failure_result_map)
