# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from services import step_util
from services import swarming
from waterfall import build_util
from waterfall import buildbot
from waterfall.build_info import BuildInfo
from waterfall.test import wf_testcase


def _MockedGetBuildInfo(master_name, builder_name, build_number):
  build = BuildInfo(master_name, builder_name, build_number)
  build.commit_position = (build_number + 1) * 10
  build.result = buildbot.SUCCESS if build_number > 4 else buildbot.EXCEPTION
  return 200, build


class StepUtilTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepExactMatch(self, *_):
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', 0, 100, 30)
    self.assertEqual(1, lower_bound.build_number)
    self.assertEqual(2, upper_bound.build_number)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=100)
  def testGetValidBoundingBuildsForStepNoLowerUpperBounds(self, *_):
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', None, None, 70)
    self.assertEqual(5, lower_bound.build_number)
    self.assertEqual(6, upper_bound.build_number)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitBeforeEarliestBuild(self, *_):
    lower_bound_build_number = 3
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', lower_bound_build_number, 100, 10)

    self.assertIsNone(lower_bound)
    self.assertEqual(lower_bound_build_number, upper_bound.build_number)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=False)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitBeforeEarliestBuildInValid(
      self, *_):
    lower_bound_build_number = 3
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', lower_bound_build_number, 100, 10)

    self.assertIsNone(lower_bound)
    self.assertIsNone(upper_bound)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitAfterLatestBuild(self, *_):
    upper_bound_build_number = 5
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', None, upper_bound_build_number, 10000)
    self.assertEqual(upper_bound_build_number, lower_bound.build_number)
    self.assertIsNone(upper_bound)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=False)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitAfterLatestBuildInvalid(self, *_):
    upper_bound_build_number = 5
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', None, upper_bound_build_number, 10000)

    self.assertIsNone(lower_bound)
    self.assertIsNone(upper_bound)

  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=10)
  @mock.patch.object(swarming, 'CanFindSwarmingTaskFromBuildForAStep')
  def testGetValidBoundingBuildsForStep(self, mock_fn, *_):
    # Original lower_bound and upper_bound should be 3 and 4, but no tasks
    # found on those builds, so lower_bound-1, upper_bound+1.
    mock_fn.side_effect = [False, True, False, True]
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', None, None, 45)

    self.assertEqual(2, lower_bound.build_number)
    self.assertEqual(5, upper_bound.build_number)

  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=None)
  def testGetValidBoundingBuildsForStepNoLatestBuild(self, *_):
    self.assertEqual((None, None),
                     step_util.GetValidBoundingBuildsForStep(
                         'm', 'b', 's', None, None, 50))
