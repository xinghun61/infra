# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.results import Result, MatchResult
from crash.scorers.min_distance import MinDistance
from crash.scorers.test.scorer_test_suite import ScorerTestSuite


class MinDistanceTest(ScorerTestSuite):

  def testGetMetric(self):
    dummy_changelog = self._GetDummyChangeLog()
    match_result = MatchResult(dummy_changelog, 'src/', '')
    match_result.min_distance = 0

    self.assertEqual(MinDistance().GetMetric(match_result), 0)

    result = Result(dummy_changelog, 'src/', '')
    self.assertEqual(MinDistance().GetMetric(result), None)

  def testScore(self):
    self.assertEqual(MinDistance().Score(0), 1)
    self.assertEqual(MinDistance().Score(30), 0.8)
    self.assertEqual(MinDistance().Score(60), 0)

  def testReason(self):
    self.assertEqual(MinDistance().Reason(0, 1),
                     'Minimum distance to crashed line is 0')
    self.assertEqual(MinDistance().Reason(60, 0),
                     '')
