# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.commit_id_range import CommitID
from dto.commit_id_range import CommitIDRange
from gae_libs.testcase import TestCase
from model.flake.analysis.data_point import DataPoint
from services import git
from services.flake_failure import flake_constants
from services.flake_failure import lookback_algorithm


class LookbackAlgorithmTest(TestCase):

  @mock.patch.object(
      git, 'GetRevisionForCommitPositionByAnotherCommit', return_value='r99')
  def testLookbackAlgorithmSingleFlakyDataPoint(self, _):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100')
    ]

    next_commit_id = CommitID(commit_position=99, revision='r99')

    self.assertEqual(
        (next_commit_id, None),  # Begins with step size 1.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  @mock.patch.object(
      git, 'GetRevisionForCommitPositionByAnotherCommit', return_value='r74')
  def testLookbackAlgorithmExponentialLookback(self, mock_git):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100'),
        DataPoint.Create(commit_position=90, pass_rate=0.5, git_hash='r90'),
    ]
    # Step size 10, rounded up to the next square == 16.
    next_commit_id = CommitID(commit_position=74, revision='r74')
    self.assertEqual(
        (next_commit_id, None),
        lookback_algorithm._DetermineNextCommitPosition(data_points))
    mock_git.assert_called_once_with('r90', 90, 74)

  @mock.patch.object(
      git, 'GetRevisionForCommitPositionByAnotherCommit', return_value='r45')
  def testLookbackAlgorithmExponentialLookbackManyDataPoints(self, mock_git):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100'),
        DataPoint.Create(commit_position=90, pass_rate=0.5, git_hash='r90'),
        DataPoint.Create(commit_position=70, pass_rate=0.5, git_hash='r70'),
    ]

    # Last Step size 20, rounded up to the next square == 25.
    next_commit_id = CommitID(commit_position=45, revision='r45')
    self.assertEqual(
        (next_commit_id, None),
        lookback_algorithm._DetermineNextCommitPosition(data_points))
    mock_git.assert_called_once_with('r70', 70, 45)

  @mock.patch.object(
      git, 'GetRevisionForCommitPositionByAnotherCommit', return_value='r99')
  def testLookbackAlgorithmWithRegressionRangeRestartExponential(
      self, mock_git):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100'),
        DataPoint.Create(commit_position=90, pass_rate=1.0, git_hash='r90'),
    ]
    # 100 stable, 90 flaky. Restart search from 99.
    next_commit_id = CommitID(commit_position=99, revision='r99')
    self.assertEqual(
        (next_commit_id, None),
        lookback_algorithm._DetermineNextCommitPosition(data_points))
    mock_git.assert_called_once_with('r100', 100, 99)

  @mock.patch.object(
      git, 'GetRevisionForCommitPositionByAnotherCommit', return_value='r74')
  def testLookbackAlgorithmWithRegressionRangeContinueExponential(
      self, mock_git):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100'),
        DataPoint.Create(commit_position=90, pass_rate=0.5, git_hash='r90'),
        DataPoint.Create(commit_position=70, pass_rate=1.0, git_hash='r70'),
    ]

    next_commit_id = CommitID(commit_position=74, revision='r74')
    self.assertEqual(
        (next_commit_id, None),
        lookback_algorithm._DetermineNextCommitPosition(data_points))
    mock_git.assert_called_once_with('r90', 90, 74)

  @mock.patch.object(
      git, 'GetRevisionForCommitPositionByAnotherCommit', return_value='r19')
  def testLookbackAlgorithmWithRegressionRangeRestartExponentialLargeStep(
      self, _):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100'),
        DataPoint.Create(commit_position=90, pass_rate=0.5, git_hash='r90'),
        DataPoint.Create(commit_position=20, pass_rate=0.5, git_hash='r20'),
        DataPoint.Create(commit_position=10, pass_rate=1.0, git_hash='r10'),
    ]

    next_commit_id = CommitID(commit_position=19, revision='r19')
    self.assertEqual(
        (next_commit_id, None),
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  @mock.patch.object(
      git, 'GetRevisionForCommitPositionByAnotherCommit', return_value='r19')
  def testLookbackAlgorithmRestartExponentialLandsOnExistingDataPoint(self, _):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100'),
        DataPoint.Create(commit_position=32, pass_rate=0.5, git_hash='r32'),
        DataPoint.Create(commit_position=20, pass_rate=0.5, git_hash='r20'),
        DataPoint.Create(commit_position=4, pass_rate=1.0, git_hash='r4'),
    ]

    next_commit_id = CommitID(commit_position=19, revision='r19')
    self.assertEqual(
        (next_commit_id, None),
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  @mock.patch.object(
      git, 'GetRevisionForCommitPositionByAnotherCommit', return_value='r75')
  def testLookbackAlgorithmBisectWhenTestDoesNotExist(self, _):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100'),
        DataPoint.Create(
            commit_position=50,
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND,
            git_hash='r50'),
    ]

    next_commit_id = CommitID(commit_position=75, revision='r75')
    self.assertEqual(
        (next_commit_id, None),  # 100 flaky, 50 non-existent. Bisect.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmNoCulpritWhenTestDoesNotExist(self):
    data_points = [
        DataPoint.Create(
            commit_position=100,
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND),
    ]

    self.assertEqual(
        (None, None),  # Test not found from the beginning.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmNoCulpritWhenNotReproducible(self):
    data_points = [DataPoint.Create(commit_position=100, pass_rate=1.0)]
    self.assertEqual(
        (None, None),  # Flakiness not reproducible from the beginning.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmCulpritFoundExistingTest(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100'),
        DataPoint.Create(commit_position=71, pass_rate=0.5, git_hash='r71'),
        DataPoint.Create(commit_position=70, pass_rate=1.0, git_hash='r70'),
    ]

    # 70 stable, 71 flaky. 71 must be the culprit.
    culprit_commit_id = CommitID(commit_position=71, revision='r71')
    self.assertEqual(
        (None, culprit_commit_id),
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmCulpritFoundNewlyAddedTest(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='r100'),
        DataPoint.Create(commit_position=71, pass_rate=0.5, git_hash='r71'),
        DataPoint.Create(
            commit_position=70,
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND,
            git_hash='r70')
    ]

    # 70 nonexistent, 71 flaky. 71 must be the culprit.
    culprit_commit_id = CommitID(commit_position=71, revision='r71')

    self.assertEqual(
        (None, culprit_commit_id),
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testBisectPoint(self):
    self.assertEqual(0, lookback_algorithm.BisectPoint(0, 1))
    self.assertEqual(1, lookback_algorithm.BisectPoint(0, 2))
    self.assertEqual(3, lookback_algorithm.BisectPoint(1, 5))
    self.assertEqual(1, lookback_algorithm.BisectPoint(1, 1))

  @mock.patch.object(git, 'GetRevisionForCommitPositionByAnotherCommit')
  def testBisectNextCommitPosition(self, mock_get_revision):
    regression_range = CommitIDRange(
        lower=CommitID(commit_position=90, revision='rev_90'),
        upper=CommitID(commit_position=100, revision='rev_100'))
    mock_get_revision.return_value = 'rev_95'

    self.assertEqual((CommitID(commit_position=95, revision='rev_95'), None),
                     lookback_algorithm._Bisect(regression_range))
    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/947753.
    # mock_get_revision.assert_callled_once_with('rev_100', 100, 95)

  def testBisectFinished(self):
    regression_range = CommitIDRange(
        lower=CommitID(commit_position=90, revision='rev_90'),
        upper=CommitID(commit_position=91, revision='rev_91'))
    self.assertEqual((None, CommitID(commit_position=91, revision='rev_91')),
                     lookback_algorithm._Bisect(regression_range))

  @mock.patch.object(git, 'GetRevisionForCommitPositionByAnotherCommit')
  def testGetNextCommitIdBisect(self, mock_get_revision):
    regression_range = CommitIDRange(
        lower=CommitID(commit_position=90, revision='rev_90'),
        upper=CommitID(commit_position=100, revision='rev_100'))
    data_points = [
        DataPoint.Create(
            commit_position=100, pass_rate=0.9, git_hash='rev_100'),
        DataPoint.Create(commit_position=90, pass_rate=1.0, git_hash='rev_90'),
    ]

    mock_get_revision.return_value = 'rev_95'
    self.assertEqual((CommitID(commit_position=95, revision='rev_95'), None),
                     lookback_algorithm.GetNextCommitId(data_points, True,
                                                        regression_range))

  @mock.patch.object(git, 'GetRevisionForCommitPositionByAnotherCommit')
  def testGetNextCommitIdExponentialSearch(self, mock_get_revision):
    regression_range = CommitIDRange(
        lower=CommitID(commit_position=90, revision='rev_90'),
        upper=CommitID(commit_position=100, revision='rev_100'))
    data_points = [
        DataPoint.Create(
            commit_position=100, pass_rate=0.9, git_hash='rev_100'),
        DataPoint.Create(commit_position=90, pass_rate=1.0, git_hash='rev_90'),
    ]
    mock_get_revision.return_value = 'rev_99'

    self.assertEqual((CommitID(commit_position=99, revision='rev_99'), None),
                     lookback_algorithm.GetNextCommitId(data_points, False,
                                                        regression_range))
