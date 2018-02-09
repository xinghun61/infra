# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from gae_libs.pipeline_wrapper import pipeline_handlers
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskOutput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    UpdateFlakeAnalysisDataPointsInput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from services.flake_failure import data_point_util
from waterfall.test.wf_testcase import WaterfallTestCase


class UpdateFlakeAnalysisDataPointsPipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(data_point_util, 'UpdateAnalysisDataPoints')
  def testUpdateFlakeAnalysisDataPointsPipeline(self, mocked_update):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()
    commit_position = 1000
    revision = 'r1000'
    swarming_task_output = RunFlakeSwarmingTaskOutput(
        error=None,
        pass_count=5,
        iterations=10,
        started_time=datetime(2018, 1, 1, 0, 0, 0),
        completed_time=datetime(2018, 1, 1, 1, 0, 0),
        has_valid_artifact=True,
        task_id='task_id')

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        revision=revision,
        swarming_task_output=swarming_task_output)

    pipeline_job = UpdateFlakeAnalysisDataPointsPipeline(
        update_data_points_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    mocked_update.assert_called_once()
