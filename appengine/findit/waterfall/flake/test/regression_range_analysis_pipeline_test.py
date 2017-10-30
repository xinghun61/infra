# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import build_util
from waterfall import buildbot
from waterfall.build_info import BuildInfo
from waterfall.flake import regression_range_analysis_pipeline
from waterfall.flake.next_build_number_pipeline import NextBuildNumberPipeline
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline
from waterfall.flake.regression_range_analysis_pipeline import (
    _CommitPositionRange)
from waterfall.flake.regression_range_analysis_pipeline import (
    RegressionRangeAnalysisPipeline)
from waterfall.test import wf_testcase


def _MockedGetBuildInfo(master_name, builder_name, build_number):
  build = BuildInfo(master_name, builder_name, build_number)
  build.commit_position = (build_number + 1) * 10
  return build


class RegressionRangeAnalysisPipelineTest(wf_testcase.WaterfallTestCase):

  app_module = pipeline_handlers._APP

  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetBoundedRangeForCommitPositionFromBuild(self):
    self.assertEqual(
        (1, 1),
        regression_range_analysis_pipeline._GetBoundedRangeFromBuild(
            20, 'm', 'b', 1))
    self.assertEqual(
        (None, 1),
        regression_range_analysis_pipeline._GetBoundedRangeFromBuild(
            5, 'm', 'b', 1))
    self.assertEqual(
        (1, None),
        regression_range_analysis_pipeline._GetBoundedRangeFromBuild(
            200, 'm', 'b', 1))

  def testGetBoundedRangeForCommitPosition(self):
    builds_to_commits = {
        1: _CommitPositionRange(11, 20),
        2: _CommitPositionRange(21, 30),
        4: _CommitPositionRange(41, 50),
        7: _CommitPositionRange(71, 80),
        11: _CommitPositionRange(111, 120)
    }

    self.assertEqual(
        (None, None),
        regression_range_analysis_pipeline._GetBoundedRangeForCommitPosition(
            1, {}))
    self.assertEqual(
        (1, 1),
        regression_range_analysis_pipeline._GetBoundedRangeForCommitPosition(
            11, builds_to_commits))
    self.assertEqual(
        (1, 1),
        regression_range_analysis_pipeline._GetBoundedRangeForCommitPosition(
            20, builds_to_commits))
    self.assertEqual(
        (2, 2),
        regression_range_analysis_pipeline._GetBoundedRangeForCommitPosition(
            25, builds_to_commits))
    self.assertEqual(
        (2, 4),
        regression_range_analysis_pipeline._GetBoundedRangeForCommitPosition(
            40, builds_to_commits))
    self.assertEqual(
        (2, 4),
        regression_range_analysis_pipeline._GetBoundedRangeForCommitPosition(
            31, builds_to_commits))
    self.assertEqual(
        (4, 7),
        regression_range_analysis_pipeline._GetBoundedRangeForCommitPosition(
            70, builds_to_commits))
    self.assertEqual(
        (None, 1),
        regression_range_analysis_pipeline._GetBoundedRangeForCommitPosition(
            1, builds_to_commits))
    self.assertEqual(
        (11, None),
        regression_range_analysis_pipeline._GetBoundedRangeForCommitPosition(
            1000, builds_to_commits))

  def testBuildNumberToCommitPositionsDict(self):
    data_point_0 = DataPoint()
    data_point_0.build_number = 0
    data_point_0.commit_position = 0

    data_point_1 = DataPoint()
    data_point_1.build_number = 1
    data_point_1.commit_position = 20
    data_point_1.previous_build_commit_position = 10

    data_point_2 = DataPoint()
    data_point_2.build_number = 2
    data_point_2.commit_position = 30
    data_point_2.previous_build_commit_position = 20

    data_point_4 = DataPoint()
    data_point_4.build_number = 4
    data_point_4.commit_position = 50
    data_point_4.previous_build_commit_position = 40

    data_points = [
        data_point_1, data_point_4, data_point_2,
        DataPoint(), data_point_0
    ]

    expected_dict = {
        1: _CommitPositionRange(11, 20),
        2: _CommitPositionRange(21, 30),
        4: _CommitPositionRange(41, 50),
    }

    builds_to_commits = (regression_range_analysis_pipeline.
                         _BuildNumbersToCommitPositionsDict(data_points))

    for build_number in builds_to_commits.iterkeys():
      self.assertEqual(expected_dict[build_number].ToDict(),
                       builds_to_commits[build_number].ToDict())

  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=6)
  def testGetEarliestBuildNumberFromRelativeBuildNumber(self, _):
    data_point_1 = DataPoint()
    data_point_1.build_number = 1
    data_point_1.commit_position = 20
    data_point_1.previous_build_commit_position = 10

    data_point_2 = DataPoint()
    data_point_2.build_number = 2
    data_point_2.commit_position = 30
    data_point_2.previous_build_commit_position = 20

    data_point_4 = DataPoint()
    data_point_4.build_number = 4
    data_point_4.commit_position = 50
    data_point_4.previous_build_commit_position = 40

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [data_point_1, data_point_2, data_point_4]

    self.assertEqual(
        6,
        regression_range_analysis_pipeline._GetEarliestContainingBuildNumber(
            100, analysis))

  @mock.patch.object(
      regression_range_analysis_pipeline,
      '_BuildNumbersToCommitPositionsDict',
      return_value={3: _CommitPositionRange(21, 30)})
  @mock.patch.object(
      regression_range_analysis_pipeline,
      '_GetBoundedRangeForCommitPosition',
      return_value=(3, 3))
  @mock.patch.object(
      build_util, 'GetBuildInfo', return_value=BuildInfo('m', 'b', 3))
  def testGetEarliestBuildNumberExactMatch(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertEqual(
        3,
        regression_range_analysis_pipeline._GetEarliestContainingBuildNumber(
            100, analysis))

  @mock.patch.object(
      regression_range_analysis_pipeline,
      '_GetBoundedRangeForCommitPosition',
      return_value=(None, None))
  @mock.patch.object(
      build_util, 'GetBuildInfo', return_value=BuildInfo('m', 'b', 123))
  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=123)
  def testGetEarliestBuildNumberNoDataPoints(self, *_):
    self.assertEqual(
        123,
        regression_range_analysis_pipeline._GetEarliestContainingBuildNumber(
            100, MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')))

  def testRemoveStablePointsFromAnalysisWithinRange(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {
        'swarming_rerun': {
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98
        }
    }
    data_points = [
        DataPoint.Create(
            pass_rate=1.0,
            build_number=100,
            commit_position=1000,
            iterations=100),
        DataPoint.Create(pass_rate=0.5, build_number=101, commit_position=1100)
    ]
    analysis.data_points = data_points
    regression_range_analysis_pipeline._RemoveStablePointsWithinRange(
        analysis, 99, 101, 200)

    self.assertEqual([data_points[1]], analysis.data_points)

  def testCanStartManualAnalysisRunningSwarming(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.status = analysis_status.RUNNING
    self.assertFalse(
        regression_range_analysis_pipeline._CanStartManualAnalysis(analysis))

  def testCanStartManualAnalysisRunningTryJob(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.RUNNING
    self.assertFalse(
        regression_range_analysis_pipeline._CanStartManualAnalysis(analysis))

  def testCanStartManualAnalysisSwarmingCompleted(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.status = analysis_status.COMPLETED
    self.assertTrue(
        regression_range_analysis_pipeline._CanStartManualAnalysis(analysis))

  def testCanStartManualAnalysisTryJobsCompleted(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.COMPLETED
    self.assertTrue(
        regression_range_analysis_pipeline._CanStartManualAnalysis(analysis))

  @mock.patch.object(
      buildbot, 'GetStepLog', return_value={'dimensions': {
          'os': 'OS'
      }})
  def testRegressionRangeAnalysisPipeline(self, _):
    input_lower_bound = 900
    input_upper_bound = 1000
    iterations_to_rerun = 200
    lower_bound_build_number = 90
    upper_bound_build_number = 100
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.SKIPPED
    analysis.algorithm_parameters = {
        'swarming_rerun': {
            'iterations_to_rerun': 100,
        }
    }
    analysis.data_points = [
        DataPoint.Create(
            commit_position=input_upper_bound,
            previous_build_commit_position=990,
            build_number=upper_bound_build_number),
        DataPoint.Create(
            commit_position=input_lower_bound,
            previous_build_commit_position=890,
            build_number=lower_bound_build_number)
    ]
    analysis.Save()

    self.MockPipeline(
        RecursiveFlakePipeline,
        'task_id',
        expected_args=[
            analysis.key.urlsafe(), upper_bound_build_number,
            lower_bound_build_number, upper_bound_build_number,
            iterations_to_rerun, {
                'dimensions': {
                    'os': 'OS'
                }
            }, False, False, None, 0, False
        ],
        expected_kwargs={})

    pipeline_job = RegressionRangeAnalysisPipeline(
        analysis.key.urlsafe(), input_lower_bound, input_upper_bound,
        iterations_to_rerun)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      buildbot, 'GetStepLog', return_value={'dimensions': {
          'os': 'OS'
      }})
  def testRegressionRangeAnalysisPipelineCantStartIfStillRunning(self, _):
    input_lower_bound = 900
    input_upper_bound = 1000
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.status = analysis_status.RUNNING
    analysis.data_points = [
        DataPoint.Create(
            commit_position=1000,
            previous_build_commit_position=990,
            build_number=100),
        DataPoint.Create(
            commit_position=900,
            previous_build_commit_position=890,
            build_number=90)
    ]
    analysis.Save()

    self.MockPipeline(
        RecursiveFlakePipeline, '', expected_args=[], expected_kwargs={})

    pipeline_job = RegressionRangeAnalysisPipeline(
        analysis.key.urlsafe(), input_lower_bound, input_upper_bound, 100)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  def testRemoveStablePointsFromAnalysisWithinRangeNoChanges(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {
        'swarming_rerun': {
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98
        }
    }
    data_points = [
        DataPoint.Create(
            pass_rate=1.0,
            build_number=100,
            commit_position=1000,
            iterations=100),
        DataPoint.Create(pass_rate=0.5, build_number=101, commit_position=1100)
    ]
    analysis.data_points = data_points
    regression_range_analysis_pipeline._RemoveStablePointsWithinRange(
        analysis, 102, 105, 50)

    self.assertEqual(data_points, analysis.data_points)

  @mock.patch.object(
      buildbot, 'GetStepLog', return_value={'dimensions': {
          'os': 'OS'
      }})
  def testRegressionRangeAnalysisPipelineEndToEnd(self, _):
    input_lower_bound = 1400
    input_upper_bound = 1450
    input_iterations_to_rerun = 200
    lower_bound_build_number = 140
    upper_bound_build_number = 145

    analysis = MasterFlakeAnalysis.Create('m', 'b', 150, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.SKIPPED
    analysis.algorithm_parameters = {
        'swarming_rerun': {
            'iterations_to_rerun': 100,
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98
        }
    }
    data_points = [
        DataPoint.Create(
            build_number=150,  # Original triggering build.
            pass_rate=0.8,  # Flaky.
            commit_position=1500,
            previous_build_commit_position=1490,
            iterations=100),
        DataPoint.Create(
            build_number=149,  # Exponential lookback.
            pass_rate=0.8,  # Still flaky.
            commit_position=1490,
            previous_build_commit_position=1480,
            iterations=100),
        DataPoint.Create(
            build_number=147,  # Exponential lookback.
            pass_rate=0.8,  # Still flaky.
            commit_position=1470,
            previous_build_commit_position=1460),
        DataPoint.Create(
            build_number=144,  # Exponential lookback.
            pass_rate=1.0,  # "Stable" however not actually.
            commit_position=1440,
            previous_build_commit_position=1430,
            iterations=100),  # Iteration count not high enough.
        DataPoint.Create(
            build_number=140,  # Exponential lookback.
            pass_rate=1.0,  # Actually stable.
            commit_position=1400,
            previous_build_commit_position=1390,
            iterations=100),
        DataPoint.Create(
            build_number=145,  # Suspeccted build.
            pass_rate=0.8,  # False positive.
            commit_position=1450,
            previous_build_commit_position=1440,
            iterations=100)
    ]
    analysis.data_points = data_points
    analysis.Save()

    self.MockPipeline(
        RecursiveFlakePipeline,
        'task_id',
        expected_args=[
            analysis.key.urlsafe(), upper_bound_build_number,
            lower_bound_build_number, upper_bound_build_number,
            input_iterations_to_rerun, {
                'dimensions': {
                    'os': 'OS'
                }
            }, False, False, None, 0, False
        ],
        expected_kwargs={})

    self.MockPipeline(
        NextBuildNumberPipeline,
        100,
        expected_args=[analysis.key.urlsafe(), 145, 140, 145, 200])

    pipeline_job = RegressionRangeAnalysisPipeline(
        analysis.key.urlsafe(), input_lower_bound, input_upper_bound,
        input_iterations_to_rerun)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    self.assertEqual(
        [
            data_points[0],
            data_points[1],
            data_points[2],
            # 3 and 4 removed due to being stable and thus unreliable.
            data_points[5]
        ],
        analysis.data_points)
