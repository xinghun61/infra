# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.int_range import IntRange
from gae_libs.testcase import TestCase
from model.flake.analysis.master_flake_analysis import DataPoint
from services.flake_failure import flake_constants
from services.flake_failure import lookback_algorithm


class LookbackAlgorithmTest(TestCase):

  def testLookbackAlgorithmSingleFlakyDataPoint(self):
    data_points = [DataPoint.Create(commit_position=100, pass_rate=0.5)]
    self.assertEqual(
        (99, None),  # Begins with step size 1.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmExponentialLookback(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(commit_position=90, pass_rate=0.5),
    ]

    self.assertEqual(
        (74, None),  # Step size 10, rounded up to the next square == 16.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmExponentialLookbackManyDataPoints(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(commit_position=90, pass_rate=0.5),
        DataPoint.Create(commit_position=70, pass_rate=0.5),
    ]

    self.assertEqual(
        (45, None),  # Last Step size 20, rounded up to the next square == 25.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmWithRegressionRangeRestartExponential(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(commit_position=90, pass_rate=1.0),
    ]

    self.assertEqual(
        (99, None),  # 100 stable, 90 flaky. Restart search from 99.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmWithRegressionRangeContinueExponential(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(commit_position=90, pass_rate=0.5),
        DataPoint.Create(commit_position=70, pass_rate=1.0),
    ]

    self.assertEqual(
        (74, None),
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmWithRegressionRangeRestartExponentialLargeStep(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(commit_position=90, pass_rate=0.5),
        DataPoint.Create(commit_position=20, pass_rate=0.5),
        DataPoint.Create(commit_position=10, pass_rate=1.0),
    ]

    self.assertEqual(
        (19, None),
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmRestartExponentialLandsOnExistingDataPoint(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(commit_position=32, pass_rate=0.5),
        DataPoint.Create(commit_position=20, pass_rate=0.5),
        DataPoint.Create(commit_position=4, pass_rate=1.0),
    ]

    self.assertEqual(
        (19, None),
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmBisectWhenTestDoesNotExist(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(
            commit_position=50,
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND),
    ]

    self.assertEqual(
        (75, None),  # 100 flaky, 50 non-existent. Bisect.
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
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(commit_position=71, pass_rate=0.5),
        DataPoint.Create(commit_position=70, pass_rate=1.0),
    ]

    self.assertEqual(
        (None, 71),  # 70 stable, 71 flaky. 71 must be the culprit.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testLookbackAlgorithmCulpritFoundNewlyAddedTest(self):
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(commit_position=71, pass_rate=0.5),
        DataPoint.Create(
            commit_position=70,
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND)
    ]

    self.assertEqual(
        (None, 71),  # 70 nonexistent, 71 flaky. 71 must be the culprit.
        lookback_algorithm._DetermineNextCommitPosition(data_points))

  def testBisectPoint(self):
    self.assertEqual(0, lookback_algorithm.BisectPoint(0, 1))
    self.assertEqual(1, lookback_algorithm.BisectPoint(0, 2))
    self.assertEqual(3, lookback_algorithm.BisectPoint(1, 5))
    self.assertEqual(1, lookback_algorithm.BisectPoint(1, 1))

  def testBisectNextCommitPosition(self):
    regression_range = IntRange(lower=90, upper=100)
    self.assertEqual((95, None), lookback_algorithm._Bisect(regression_range))

  def testBisectFinished(self):
    regression_range = IntRange(lower=90, upper=91)
    self.assertEqual((None, 91), lookback_algorithm._Bisect(regression_range))

  def testGetNextCommitPositionBisect(self):
    regression_range = IntRange(lower=90, upper=100)
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.9),
        DataPoint.Create(commit_position=90, pass_rate=1.0),
    ]

    self.assertEqual((95, None),
                     lookback_algorithm.GetNextCommitPosition(
                         data_points, True, regression_range))

  def testGetNextCommitPositionExponentialSearch(self):
    regression_range = IntRange(lower=90, upper=100)
    data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.9),
        DataPoint.Create(commit_position=90, pass_rate=1.0),
    ]

    self.assertEqual((99, None),
                     lookback_algorithm.GetNextCommitPosition(
                         data_points, False, regression_range))
