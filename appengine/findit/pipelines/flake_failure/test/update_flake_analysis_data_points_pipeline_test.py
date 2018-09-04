# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.flakiness import Flakiness
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs.list_of_basestring import ListOfBasestring
from model.flake.analysis.master_flake_analysis import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsInput)
from pipelines.flake_failure.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from services.flake_failure import flakiness_util
from services.flake_failure import run_swarming_util
from waterfall.test.wf_testcase import WaterfallTestCase


class UpdateFlakeAnalysisDataPointsPipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testUpdateFlakeAnalysisDataPointsPipeline(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    commit_position = 1000
    pass_rate = 0.5

    flakiness = Flakiness(
        build_number=123,
        build_url='url',
        commit_position=commit_position,
        total_test_run_seconds=100,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=50,
        pass_rate=pass_rate,
        revision='r1000',
        try_job_url=None,
        task_ids=ListOfBasestring.FromSerializable(['task_id']))

    expected_data_point = DataPoint.Create(
        build_number=123,
        build_url='url',
        commit_position=commit_position,
        elapsed_seconds=100,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=50,
        pass_rate=pass_rate,
        git_hash='r1000',
        try_job_url=None,
        task_ids=['task_id'])

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), flakiness=flakiness)

    pipeline_job = UpdateFlakeAnalysisDataPointsPipeline(
        update_data_points_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertEqual(1, len(analysis.data_points))
    self.assertEqual(expected_data_point, analysis.data_points[0])

  @mock.patch.object(
      flakiness_util, 'MaximumSwarmingTaskRetriesReached', return_value=True)
  @mock.patch.object(run_swarming_util, 'ReportSwarmingTaskError')
  def testUpdateFlakeAnalysisDataPointsPipelineTooManyErrors(
      self, _, mocked_error_reporting):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    flakiness = Flakiness(
        build_number=None,
        build_url='url',
        commit_position=1000,
        total_test_run_seconds=100,
        error=None,
        failed_swarming_task_attempts=3,
        iterations=50,
        pass_rate=0.5,
        revision='r1000',
        try_job_url=None,
        task_ids=ListOfBasestring.FromSerializable(['task_id']))

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), flakiness=flakiness)

    pipeline_job = UpdateFlakeAnalysisDataPointsPipeline(
        update_data_points_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(mocked_error_reporting.called)
