# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from services.flake_failure import confidence_score_util
from services.flake_failure import confidence
from services.flake_failure import flake_constants
from waterfall.test.wf_testcase import WaterfallTestCase


class ConfidenceScoreUtilTest(WaterfallTestCase):

  @mock.patch.object(
      confidence, 'SteppinessForCommitPosition', return_value=0.6)
  def testCalculateCulpritConfidenceScore(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 124, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.7, iterations=10, commit_position=1000),
        DataPoint.Create(pass_rate=1.0, iterations=400, commit_position=999)
    ]
    self.assertIsNone(
        confidence_score_util.CalculateCulpritConfidenceScore(analysis, None))
    self.assertEqual(
        0.6,
        confidence_score_util.CalculateCulpritConfidenceScore(analysis, 1000))

  def testCalculateCulpritConfidenceScoreIntroducedNewFlakyTest(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 124, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.7, commit_position=1000),
        DataPoint.Create(
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND,
            commit_position=999)
    ]
    self.assertEqual(
        1.0,
        confidence_score_util.CalculateCulpritConfidenceScore(analysis, 1000))

  def testCalculateCulpritConfidenceScoreIntroducedStableToFlaky(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 124, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.7, iterations=10, commit_position=1000),
        DataPoint.Create(pass_rate=1.0, iterations=400, commit_position=999),
        DataPoint.Create(pass_rate=1.0, iterations=400, commit_position=996)
    ]
    self.assertEqual(
        .7, confidence_score_util.CalculateCulpritConfidenceScore(
            analysis, 1000))

  def testCalculateCulpritConfidenceScoreLowFlakiness(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 124, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=0.9975, iterations=400, commit_position=1000),
        DataPoint.Create(pass_rate=1.0, iterations=400, commit_position=999)
    ]
    self.assertIsNone(
        confidence_score_util.CalculateCulpritConfidenceScore(analysis, None))
    self.assertEqual(
        0.0,
        confidence_score_util.CalculateCulpritConfidenceScore(analysis, 1000))

  @mock.patch.object(
      confidence, 'SteppinessForCommitPosition', return_value=0.6)
  def testCalculateCulpritConfidenceScoreFallbackToSteppiness(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 124, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.7, iterations=20, commit_position=1000),
        DataPoint.Create(pass_rate=1.0, iterations=400, commit_position=999),
    ]
    self.assertEqual(
        .6, confidence_score_util.CalculateCulpritConfidenceScore(
            analysis, 1000))
