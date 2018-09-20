# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from dto.flakiness import Flakiness
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import Contributor
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

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testUpdateFlakeAnalysisDataPointsPipeline(self, mocked_change_log):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    commit_position = 1000
    pass_rate = 0.5
    revision = 'r1000'
    expected_time = datetime(2018, 9, 18, 0, 0, 0)
    committer = Contributor(name='name', email='email', time=expected_time)
    change_log = ChangeLog(None, committer, revision, None, None, None, None,
                           None)
    mocked_change_log.return_value = change_log

    flakiness = Flakiness(
        build_number=123,
        build_url='url',
        commit_position=commit_position,
        total_test_run_seconds=100,
        error=None,
        failed_swarming_task_attempts=0,
        iterations=50,
        pass_rate=pass_rate,
        revision=revision,
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
        git_hash=revision,
        try_job_url=None,
        task_ids=['task_id'],
        commit_position_landed_time=expected_time)

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
