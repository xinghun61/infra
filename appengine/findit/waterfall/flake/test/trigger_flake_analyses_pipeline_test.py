# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from gae_libs.pipeline_wrapper import pipeline_handlers
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from waterfall.flake import flake_analysis_service
from waterfall.flake.trigger_flake_analyses_pipeline import (
    TriggerFlakeAnalysesPipeline)
from waterfall.test import wf_testcase


class TriggerFlakeAnalysesPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testTriggerFlakeAnalysesPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    step_name = 'a_tests'
    test_name = 'Unittest1.Subtest1'

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        step_name: {
            test_name: '%s/%s/%s' % (master_name, builder_name, build_number)
        }
    }
    analysis.put()

    swarming_task = WfSwarmingTask.Create(
        master_name, builder_name, build_number, step_name)
    swarming_task.tests_statuses = {
        test_name: {'SUCCESS': 1}
    }
    swarming_task.put()

    with mock.patch.object(
        flake_analysis_service,'ScheduleAnalysisForFlake') as (
             mocked_ScheduleAnalysisForFlake):
      pipeline = TriggerFlakeAnalysesPipeline()
      pipeline.run(master_name, builder_name, build_number)
      mocked_ScheduleAnalysisForFlake.assert_called_once()
