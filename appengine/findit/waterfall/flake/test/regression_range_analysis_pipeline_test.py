# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import build_util
from waterfall import buildbot
from waterfall.build_info import BuildInfo
from waterfall.flake import regression_range_analysis_pipeline
from waterfall.flake.regression_range_analysis_pipeline import (
    _CommitPositionRange)
from waterfall.test import wf_testcase


def _MockedGetBuildInfo(master_name, builder_name, build_number):
  build = BuildInfo(master_name, builder_name, build_number)
  build.commit_position = (build_number + 1) * 10
  return build


class RegressionRangeAnalysisPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      regression_range_analysis_pipeline, '_GetBuildInfo', _MockedGetBuildInfo)
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

    data_points = [data_point_1, data_point_4, data_point_2, DataPoint(),
                   data_point_0]

    expected_dict = {
        1: _CommitPositionRange(11, 20),
        2: _CommitPositionRange(21, 30),
        4: _CommitPositionRange(41, 50),
    }

    builds_to_commits = (
        regression_range_analysis_pipeline._BuildNumbersToCommitPositionsDict(
            data_points))

    for build_number in builds_to_commits.iterkeys():
      self.assertEqual(
          expected_dict[build_number].ToDict(),
          builds_to_commits[build_number].ToDict())

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetBuildInfo(self, mocked_fn):
    build_info = BuildInfo('m', 'b', 123)
    build_info.commit_position = 100
    mocked_fn.return_value = build_info

    self.assertEqual(
        123,
        regression_range_analysis_pipeline._GetBuildInfo(
            'm', 'b', 123).build_number)

  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[10, 9])
  def testGetLatestBuildNumber(self, _):
    self.assertEqual(
        10,
        regression_range_analysis_pipeline._GetLatestBuildNumber('m', 'b'))

  @mock.patch.object(
      regression_range_analysis_pipeline, '_GetBuildInfo', _MockedGetBuildInfo)
  @mock.patch.object(regression_range_analysis_pipeline,
                     '_GetLatestBuildNumber', return_value=11)
  def testGetNearestBuild(self, _):
    # Test exact match.
    self.assertEqual(
        2,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', 2, 2, 30).build_number)

    self.assertEqual(
        2,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', 1, 10, 30).build_number)

    self.assertEqual(
        3,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', 0, 10, 35).build_number)

    self.assertEqual(
        4,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', 1, 9, 45).build_number)

    self.assertEqual(
        5,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', 0, 10, 60).build_number)

    self.assertEqual(
        11,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', 0, None, 1000).build_number)

    self.assertEqual(
        0,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', None, 6, 1).build_number)

    self.assertEqual(
        1,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', None, 6, 12).build_number)

    self.assertEqual(
        3,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', 1, None, 35).build_number)

    self.assertEqual(
        4,
        regression_range_analysis_pipeline._GetNearestBuild(
            'm', 'b', 2, 6, 50).build_number)

  @mock.patch.object(
      regression_range_analysis_pipeline, '_GetBuildInfo', _MockedGetBuildInfo)
  @mock.patch.object(regression_range_analysis_pipeline,
                     '_GetLatestBuildNumber', return_value=6)
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
        regression_range_analysis_pipeline._GetEarliestContainingBuild(
            100, analysis).build_number)

  @mock.patch.object(regression_range_analysis_pipeline,
                     '_BuildNumbersToCommitPositionsDict',
                     return_value={3: _CommitPositionRange(21, 30)})
  @mock.patch.object(regression_range_analysis_pipeline,
                     '_GetBoundedRangeForCommitPosition',
                     return_value=(3, 3))
  @mock.patch.object(regression_range_analysis_pipeline,
                     '_GetBuildInfo', return_value=BuildInfo('m', 'b', 3))
  def testGetEarliestBuildNumberExactMatch(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertEqual(
        3,
        regression_range_analysis_pipeline._GetEarliestContainingBuild(
            100, analysis).build_number)

  @mock.patch.object(regression_range_analysis_pipeline,
                     '_GetBoundedRangeForCommitPosition',
                     return_value=(None, None))
  @mock.patch.object(regression_range_analysis_pipeline,
                     '_GetBuildInfo', return_value=BuildInfo('m', 'b', 123))
  @mock.patch.object(regression_range_analysis_pipeline,
                     '_GetLatestBuildNumber', return_value=123)
  def testGetEarliestBuildNumberNoDataPoints(self, *_):
    self.assertEqual(
        123,
        regression_range_analysis_pipeline._GetEarliestContainingBuild(
            100,
            MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')).build_number)
