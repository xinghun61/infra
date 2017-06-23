# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from model.flake.master_flake_analysis import DataPoint
from waterfall.flake import confidence
from waterfall.test import wf_testcase


class ConfidenceTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(confidence.find_step, 'Steppiness')
  def testSplitIndexNotExists(self, mocked_steppiness):
    data_points = [
        DataPoint(build_number=99, pass_rate=0.95),
        DataPoint(build_number=100, pass_rate=0.9),
    ]
    self.assertRaises(AssertionError, confidence._Steppiness, data_points,
                      lambda x: x.build_number, 90)
    mocked_steppiness.assert_not_called()

  @mock.patch.object(confidence.find_step, 'Steppiness')
  def testNotEnoughData(self, mocked_steppiness):
    data_points = [
        DataPoint(build_number=99, pass_rate=0.95),
        DataPoint(build_number=100, pass_rate=0.9),
    ]
    steppiness = confidence._Steppiness(data_points, lambda x: x.build_number,
                                        100)
    self.assertEqual(0, steppiness)
    mocked_steppiness.assert_not_called()

  @mock.patch.object(confidence.find_step, 'Steppiness')
  def testPaddingDataPoints(self, mocked_steppiness):
    data_points = [
        DataPoint(build_number=99, pass_rate=-1),
        DataPoint(build_number=100, pass_rate=0.5),
    ]
    mocked_steppiness.side_effect = [1]
    steppiness = confidence._Steppiness(data_points, lambda x: x.build_number,
                                        100)
    self.assertEqual(1, steppiness)
    mocked_steppiness.assert_called_once_with([1, 1, 1, 1, 0.5], 4)

  @mock.patch.object(confidence.find_step, 'Steppiness')
  def testBuildNumber(self, mocked_steppiness):
    data_points = [
        DataPoint(build_number=90, pass_rate=1),
        DataPoint(build_number=94, pass_rate=1),
        DataPoint(build_number=94, pass_rate=0.5, try_job_url='http://'),
        DataPoint(build_number=97, pass_rate=1),
        DataPoint(build_number=99, pass_rate=1),
        DataPoint(build_number=100, pass_rate=1),
    ]
    mocked_steppiness.side_effect = [0]
    steppiness = confidence.SteppinessForBuild(data_points, 99)
    self.assertEqual(0, steppiness)
    mocked_steppiness.assert_called_once_with([1, 1, 1, 1, 1], 3)

  @mock.patch.object(confidence.find_step, 'Steppiness')
  def testCommitPosition(self, mocked_steppiness):
    data_points = [
        DataPoint(commit_position=90, pass_rate=1),
        DataPoint(commit_position=94, pass_rate=1),
        DataPoint(commit_position=97, pass_rate=1),
        DataPoint(commit_position=99, pass_rate=1),
        DataPoint(commit_position=100, pass_rate=1),
    ]
    mocked_steppiness.side_effect = [0]
    steppiness = confidence.SteppinessForCommitPosition(data_points, 99)
    self.assertEqual(0, steppiness)
    mocked_steppiness.assert_called_once_with([1, 1, 1, 1, 1], 3)
