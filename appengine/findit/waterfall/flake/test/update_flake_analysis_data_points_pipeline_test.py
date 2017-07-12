# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import mock

from common import constants
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import build_util
from waterfall.build_info import BuildInfo
from waterfall.flake import update_flake_analysis_data_points_pipeline
from waterfall.flake.update_flake_analysis_data_points_pipeline import (
    _TEST_DOES_NOT_EXIST)
from waterfall.flake.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from waterfall.test import wf_testcase


class UpdateFlakeAnalysisDataPointsPipelineTest(wf_testcase.WaterfallTestCase):

  app_module = pipeline_handlers._APP

  @mock.patch.object(
      CachedGitilesRepository,
      'GetCommitsBetweenRevisions',
      return_value=['r4', 'r3', 'r2', 'r1'])
  def testGetCommitsBetweenRevisions(self, _):
    self.assertEqual(
        update_flake_analysis_data_points_pipeline._GetCommitsBetweenRevisions(
            'r0', 'r4'), ['r1', 'r2', 'r3', 'r4'])

  def testGetPassRateTestDoesNotExist(self):
    task = FlakeSwarmingTask.Create('m', 'b', 123, 's', 't')
    task.tries = 0
    self.assertEqual(
        _TEST_DOES_NOT_EXIST,
        update_flake_analysis_data_points_pipeline._GetPassRate(task))

  def testGetPassRate(self):
    task = FlakeSwarmingTask.Create('m', 'b', 123, 's', 't')
    task.successes = 50
    task.tries = 100
    self.assertEqual(
        0.5, update_flake_analysis_data_points_pipeline._GetPassRate(task))

  @mock.patch.object(update_flake_analysis_data_points_pipeline,
                     '_GetCommitsBetweenRevisions')
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testCreateDataPointWithPrevious(self, mocked_build_info, mocked_commits):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    task_id = 'task_id'
    has_valid_artifact = True
    tries = 100
    successes = 50
    chromium_revision = 'r1000'
    commit_position = 1000
    blame_list = [
        'r1000', 'r999', 'r998', 'r997', 'r996', 'r995', 'r994', 'r993', 'r992',
        'r991'
    ]

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.task_id = task_id
    task.has_valid_artifact = has_valid_artifact
    task.tries = tries
    task.successes = successes

    build_info_122 = BuildInfo(master_name, builder_name, build_number)
    build_info_122.commit_position = commit_position - 10
    build_info_122.chromium_revision = 'r990'
    build_info_123 = BuildInfo(master_name, builder_name, build_number)
    build_info_123.commit_position = commit_position
    build_info_123.chromium_revision = chromium_revision

    mocked_build_info.side_effect = [build_info_123, build_info_122]
    mocked_commits.return_value = blame_list

    data_point = update_flake_analysis_data_points_pipeline._CreateDataPoint(
        task)

    self.assertEqual(build_number, data_point.build_number)
    self.assertEqual(0.5, data_point.pass_rate)
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(chromium_revision, data_point.git_hash)
    self.assertEqual('r990', data_point.previous_build_git_hash)
    self.assertEqual(990, data_point.previous_build_commit_position)
    self.assertEqual(blame_list, data_point.blame_list)

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testCreateDataPointNoPreviousBuild(self, mocked_build_info):
    master_name = 'm'
    builder_name = 'b'
    build_number = 0
    step_name = 's'
    test_name = 't'
    task_id = 'task_id'
    has_valid_artifact = True
    tries = 100
    successes = 50
    chromium_revision = 'r1000'
    commit_position = 1000
    blame_list = [
        'r1000', 'r999', 'r998', 'r997', 'r996', 'r995', 'r994', 'r993', 'r992',
        'r991'
    ]

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.task_id = task_id
    task.has_valid_artifact = has_valid_artifact
    task.tries = tries
    task.successes = successes

    build_info = BuildInfo(master_name, builder_name, build_number)
    build_info.commit_position = commit_position
    build_info.chromium_revision = chromium_revision
    build_info.blame_list = blame_list

    mocked_build_info.return_value = build_info

    data_point = update_flake_analysis_data_points_pipeline._CreateDataPoint(
        task)

    self.assertEqual(build_number, data_point.build_number)
    self.assertEqual(0.5, data_point.pass_rate)
    self.assertEqual(commit_position, data_point.commit_position)
    self.assertEqual(chromium_revision, data_point.git_hash)
    self.assertIsNone(data_point.previous_build_git_hash)
    self.assertIsNone(data_point.previous_build_commit_position)
    self.assertEqual(blame_list, data_point.blame_list)

  @mock.patch.object(update_flake_analysis_data_points_pipeline,
                     '_CreateDataPoint')
  def testUpdateFlakeAnalysisDataPointsPipeline(self, mocked_create_data_point):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    tries = 100
    successes = 50
    task_id = 'task_id'
    has_valid_artifact = True
    commit_position = 1000
    git_hash = 'r1000'
    previous_build_commit_position = 990
    previous_build_git_hash = 'r990'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.put()

    flake_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.tries = tries
    flake_swarming_task.successes = successes
    flake_swarming_task.put()

    expected_data_point = DataPoint.Create(
        pass_rate=0.5,
        build_number=build_number,
        task_id=task_id,
        commit_position=commit_position,
        git_hash=git_hash,
        previous_build_git_hash=previous_build_git_hash,
        previous_build_commit_position=previous_build_commit_position,
        has_valid_artifact=has_valid_artifact)

    mocked_create_data_point.return_value = expected_data_point

    pipeline_job = UpdateFlakeAnalysisDataPointsPipeline(
        analysis.key.urlsafe(), build_number)

    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertEqual(len(analysis.data_points), 1)
    self.assertIn(expected_data_point, analysis.data_points)
    self.assertIsNotNone(analysis.swarming_rerun_results)
