# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.int_range import IntRange
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from services.flake_failure import next_commit_position_utils
from waterfall.test import wf_testcase


class NextCommitPositionUtilsTest(wf_testcase.WaterfallTestCase):

  def testGetEarliestCommitPosition(self):
    self.assertEqual(0,
                     next_commit_position_utils.GetEarliestCommitPosition(
                         None, 1))
    self.assertEqual(5000,
                     next_commit_position_utils.GetEarliestCommitPosition(
                         None, 10000))
    self.assertEqual(10,
                     next_commit_position_utils.GetEarliestCommitPosition(
                         10, 11))

  def testGetNextCommitPositionFromHeuristicResultsNoResults(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.put()

    self.assertIsNone(
        next_commit_position_utils.GetNextCommitPositionFromHeuristicResults(
            analysis.key.urlsafe()))

  def testGetNextCommitPositionFromHeuristicResultsNoDataPoints(self):
    suspect = FlakeCulprit.Create('repo', 'revision', 1000)
    suspect.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.put()

    self.assertEqual(
        999,
        next_commit_position_utils.GetNextCommitPositionFromHeuristicResults(
            analysis.key.urlsafe()))

  def testGetNextCommitPositionFromHeuristicResultsAlreadyFlaky(self):
    suspect = FlakeCulprit.Create('repo', 'revision', 1000)
    suspect.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.data_points = [
        DataPoint.Create(commit_position=999, pass_rate=0.5)
    ]
    analysis.put()

    self.assertIsNone(
        next_commit_position_utils.GetNextCommitPositionFromHeuristicResults(
            analysis.key.urlsafe()))

  def testGetNextCommitPositionFromHeuristicResultsExistingDataPoints(self):
    suspect = FlakeCulprit.Create('repo', 'revision', 1000)
    suspect.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.data_points = [
        DataPoint.Create(commit_position=999, pass_rate=1.0),
        DataPoint.Create(commit_position=1000, pass_rate=1.0)
    ]
    analysis.put()

    self.assertIsNone(
        next_commit_position_utils.GetNextCommitPositionFromHeuristicResults(
            analysis.key.urlsafe()))

  def testGetNextCommitPositionFromHeuristicResults(self):
    suspect = FlakeCulprit.Create('repo', 'revision', 1000)
    suspect.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.data_points = [
        DataPoint.Create(commit_position=999, pass_rate=1.0)
    ]
    analysis.put()

    self.assertEqual(
        1000,
        next_commit_position_utils.GetNextCommitPositionFromHeuristicResults(
            analysis.key.urlsafe()))

  def testGetNextCommitPositionFromBuildRangeReturnUpperBoundCloser(self):
    calculated_commit_position = 1007
    build_range = IntRange(lower=1000, upper=1010)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1020),  # Doesn't have either.
    ]

    self.assertEqual(
        1010,
        next_commit_position_utils.GetNextCommitPositionFromBuildRange(
            analysis, build_range, calculated_commit_position))

  def testGetNextCommitPositionFromBuildRangeReturnLowerBoundCloser(self):
    calculated_commit_position = 1002
    build_range = IntRange(lower=1000, upper=1010)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1020),  # Doesn't have either.
    ]

    self.assertEqual(
        1000,
        next_commit_position_utils.GetNextCommitPositionFromBuildRange(
            analysis, build_range, calculated_commit_position))

  def testGetNextCommitPositionFromBuildRangeReturnLowerBound(self):
    calculated_commit_position = 1006
    build_range = IntRange(lower=1000, upper=1010)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1010),  # Already has upper bound.
    ]

    self.assertEqual(
        1000,
        next_commit_position_utils.GetNextCommitPositionFromBuildRange(
            analysis, build_range, calculated_commit_position))

  def testGetNextCommitPositionFromBuildRangeAlreadyHasLowerReturnUpper(self):
    calculated_commit_position = 1002
    build_range = IntRange(lower=1000, upper=1010)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1000),  # Already has lower bound.
    ]

    self.assertEqual(
        1010,
        next_commit_position_utils.GetNextCommitPositionFromBuildRange(
            analysis, build_range, calculated_commit_position))

  def testGetNextCommitPositionFromBuildRangeReturnCalculated(self):
    calculated_commit_position = 1005
    build_range = IntRange(lower=1000, upper=1010)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1010),  # Already has both.
        DataPoint.Create(commit_position=1000),
    ]

    self.assertEqual(
        calculated_commit_position,
        next_commit_position_utils.GetNextCommitPositionFromBuildRange(
            analysis, build_range, calculated_commit_position))
