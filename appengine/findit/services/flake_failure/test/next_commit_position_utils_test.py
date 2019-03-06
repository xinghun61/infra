# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.commit_id_range import CommitID
from dto.commit_id_range import CommitIDRange
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.isolated_target import IsolatedTarget
from services import git
from services.flake_failure import next_commit_position_utils
from waterfall.test import wf_testcase


class NextCommitPositionUtilsTest(wf_testcase.WaterfallTestCase):

  def testGetEarliestCommitPosition(self):
    self.assertEqual(
        0, next_commit_position_utils.GetEarliestCommitPosition(None, 1))
    self.assertEqual(
        5000, next_commit_position_utils.GetEarliestCommitPosition(None, 10000))
    self.assertEqual(
        10, next_commit_position_utils.GetEarliestCommitPosition(10, 11))

  def testGetNextCommitIdFromHeuristicResultsNoResults(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.put()

    self.assertIsNone(
        next_commit_position_utils.GetNextCommitIdFromHeuristicResults(
            analysis.key.urlsafe()))

  @mock.patch.object(
      git, 'GetRevisionForCommitPositionByAnotherCommit', return_value='r999')
  def testGetNextCommitIdFromHeuristicResultsNoDataPoints(self, _):
    suspect = FlakeCulprit.Create('repo', 'revision', 1000)
    suspect.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.put()

    next_commit_id = CommitID(commit_position=999, revision='r999')
    self.assertEqual(
        next_commit_id,
        next_commit_position_utils.GetNextCommitIdFromHeuristicResults(
            analysis.key.urlsafe()))

  def testGetNextCommitIdFromHeuristicResultsAlreadyFlaky(self):
    suspect = FlakeCulprit.Create('repo', 'revision', 1000)
    suspect.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.data_points = [
        DataPoint.Create(commit_position=999, pass_rate=0.5)
    ]
    analysis.put()

    self.assertIsNone(
        next_commit_position_utils.GetNextCommitIdFromHeuristicResults(
            analysis.key.urlsafe()))

  def testGetNextCommitIdFromHeuristicResultsExistingDataPoints(self):
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
        next_commit_position_utils.GetNextCommitIdFromHeuristicResults(
            analysis.key.urlsafe()))

  def testGetNextCommitIdFromHeuristicResults(self):
    suspect = FlakeCulprit.Create('repo', 'revision', 1000)
    suspect.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspect_urlsafe_keys.append(suspect.key.urlsafe())
    analysis.data_points = [
        DataPoint.Create(commit_position=999, pass_rate=1.0)
    ]
    analysis.put()

    next_commit_id = CommitID(commit_position=1000, revision='revision')
    self.assertEqual(
        next_commit_id,
        next_commit_position_utils.GetNextCommitIdFromHeuristicResults(
            analysis.key.urlsafe()))

  def testGetNextCommitIDFromBuildRangeReturnUpperBoundCloser(self):
    calculated_commit_id = CommitID(commit_position=1007, revision='r1007')
    lower = CommitID(commit_position=1000, revision='r1000')
    upper = CommitID(commit_position=1010, revision='r1010')
    build_range = CommitIDRange(lower=lower, upper=upper)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1020),  # Doesn't have either.
    ]

    self.assertEqual(
        upper,
        next_commit_position_utils.GetNextCommitIDFromBuildRange(
            analysis, build_range, calculated_commit_id))

  def testGetNextCommitIDFromBuildRangeReturnLowerBoundCloser(self):
    calculated_commit_id = CommitID(commit_position=1002, revision='r1002')
    lower = CommitID(commit_position=1000, revision='r1000')
    upper = CommitID(commit_position=1010, revision='r1010')
    build_range = CommitIDRange(lower=lower, upper=upper)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1020),  # Doesn't have either.
    ]

    self.assertEqual(
        lower,
        next_commit_position_utils.GetNextCommitIDFromBuildRange(
            analysis, build_range, calculated_commit_id))

  def testGetNextCommitIDFromBuildRangeReturnLowerBound(self):
    calculated_commit_id = CommitID(commit_position=1006, revision='r1006')
    lower = CommitID(commit_position=1000, revision='r1000')
    upper = CommitID(commit_position=1010, revision='r1010')
    build_range = CommitIDRange(lower=lower, upper=upper)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1010),  # Already has upper bound.
    ]

    self.assertEqual(
        lower,
        next_commit_position_utils.GetNextCommitIDFromBuildRange(
            analysis, build_range, calculated_commit_id))

  def testGetNextCommitIDFromBuildRangeAlreadyHasLowerReturnUpper(self):
    calculated_commit_id = CommitID(commit_position=1002, revision='r1002')
    lower = CommitID(commit_position=1000, revision='r1000')
    upper = CommitID(commit_position=1010, revision='r1010')
    build_range = CommitIDRange(lower=lower, upper=upper)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1000),  # Already has lower bound.
    ]

    self.assertEqual(
        upper,
        next_commit_position_utils.GetNextCommitIDFromBuildRange(
            analysis, build_range, calculated_commit_id))

  def testGetNextCommitIDFromBuildRangeReturnCalculated(self):
    calculated_commit_id = CommitID(commit_position=1005, revision='r1005')
    lower = CommitID(commit_position=1000, revision='r1000')
    upper = CommitID(commit_position=1010, revision='r1010')
    build_range = CommitIDRange(lower=lower, upper=upper)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1010),  # Already has both.
        DataPoint.Create(commit_position=1000),
    ]

    self.assertEqual(
        calculated_commit_id,
        next_commit_position_utils.GetNextCommitIDFromBuildRange(
            analysis, build_range, calculated_commit_id))

  def testGenerateCommitIDsForBoundingTargets(self):
    data_points = []
    lower_bound_target = IsolatedTarget.Create(67890, '', '', 'm', 'b', '', '',
                                               '', '', '', '', 1000, 'r1000')
    upper_bound_target = IsolatedTarget.Create(67890, '', '', 'm', 'b', '', '',
                                               '', '', '', '', 1010, 'r1010')

    lower_bound_commit_id = CommitID(commit_position=1000, revision='r1000')
    upper_bound_commit_id = CommitID(commit_position=1010, revision='r1010')
    self.assertEqual(
        (lower_bound_commit_id, upper_bound_commit_id),
        next_commit_position_utils.GenerateCommitIDsForBoundingTargets(
            data_points, lower_bound_target, upper_bound_target))

  def testGenerateCommitIDsForBoundingTargetsWithMatchPoint(self):
    data_points = [
        DataPoint.Create(commit_position=1010, git_hash='r1010'),
        DataPoint.Create(commit_position=1000, git_hash='r1000'),
    ]
    lower_bound_target = IsolatedTarget.Create(67890, '', '', 'm', 'b', '', '',
                                               '', '', '', '', 1000, None)
    upper_bound_target = IsolatedTarget.Create(67890, '', '', 'm', 'b', '', '',
                                               '', '', '', '', 1010, None)

    lower_bound_commit_id = CommitID(commit_position=1000, revision='r1000')
    upper_bound_commit_id = CommitID(commit_position=1010, revision='r1010')
    self.assertEqual(
        (lower_bound_commit_id, upper_bound_commit_id),
        next_commit_position_utils.GenerateCommitIDsForBoundingTargets(
            data_points, lower_bound_target, upper_bound_target))

  @mock.patch.object(git, 'MapCommitPositionsToGitHashes')
  def testGenerateCommitIDsForBoundingTargetsQueryGit(self, mock_revisions):
    data_points = [
        DataPoint.Create(commit_position=1010, git_hash='r1010'),
        DataPoint.Create(commit_position=1000, git_hash='r1000'),
    ]

    mock_revisions.return_value = {
        1003: 'r1003',
        1004: 'r1004',
        1005: 'r1005',
        1006: 'r1006',
        1007: 'r1007',
        1008: 'r1008',
        1009: 'r1009',
        1010: 'r1010'
    }

    lower_bound_target = IsolatedTarget.Create(67890, '', '', 'm', 'b', '', '',
                                               '', '', '', '', 1003, None)
    upper_bound_target = IsolatedTarget.Create(67890, '', '', 'm', 'b', '', '',
                                               '', '', '', '', 1008, None)

    lower_bound_commit_id = CommitID(commit_position=1003, revision='r1003')
    upper_bound_commit_id = CommitID(commit_position=1008, revision='r1008')

    self.assertEqual(
        (lower_bound_commit_id, upper_bound_commit_id),
        next_commit_position_utils.GenerateCommitIDsForBoundingTargets(
            data_points, lower_bound_target, upper_bound_target))
    mock_revisions.assert_called_once_with('r1010', 1010, 1003)
