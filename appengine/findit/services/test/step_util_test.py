# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from libs.test_results.gtest_test_results import GtestTestResults
from libs.test_results.webkit_layout_test_results import WebkitLayoutTestResults
from model.isolated_target import IsolatedTarget
from services import step_util
from services import swarming
from waterfall import build_util
from waterfall import buildbot
from waterfall import waterfall_config
from waterfall.build_info import BuildInfo
from waterfall.test import wf_testcase


def _MockedGetBuildInfo(master_name, builder_name, build_number):
  build = BuildInfo(master_name, builder_name, build_number)
  build.commit_position = (build_number + 1) * 10
  build.result = buildbot.SUCCESS if build_number > 4 else buildbot.EXCEPTION
  return 200, build


class StepUtilTest(wf_testcase.WaterfallTestCase):

  def testGetLowerBoundBuildNumber(self):
    self.assertEqual(5, step_util._GetLowerBoundBuildNumber(5, 100))
    self.assertEqual(50, step_util._GetLowerBoundBuildNumber(None, 100, 200))
    self.assertEqual(100, step_util._GetLowerBoundBuildNumber(None, 600, 500))

  def testGetBoundingIsolatedTargets(self):
    lower_bound_commit_position = 1000
    upper_bound_commit_position = 1010
    requested_commit_position = 1005
    build_id = 10000
    target_name = 'browser_tests'
    master_name = 'm'
    builder_name = 'b'
    luci_name = 'chromium'
    bucket_name = 'ci'
    gitiles_host = 'chromium.googlesource.com'
    gitiles_project = 'chromium/src'
    gitiles_ref = 'refs/heads/master'
    gerrit_patch = ''

    lower_bound_target = IsolatedTarget.Create(
        build_id - 1, luci_name, bucket_name, master_name, builder_name,
        gitiles_host, gitiles_project, gitiles_ref, gerrit_patch, target_name,
        'hash_1', lower_bound_commit_position)
    lower_bound_target.put()

    upper_bound_target = IsolatedTarget.Create(
        build_id, luci_name, bucket_name, master_name, builder_name,
        gitiles_host, gitiles_project, gitiles_ref, gerrit_patch, target_name,
        'hash_2', upper_bound_commit_position)
    upper_bound_target.put()

    self.assertEqual((lower_bound_target, upper_bound_target),
                     step_util.GetBoundingIsolatedTargets(
                         master_name, builder_name, target_name,
                         requested_commit_position))

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetValidBuildSearchAscendingWithinRange(self, mocked_get_build_info):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'

    invalid_build_100 = BuildInfo(master_name, builder_name, 100)
    invalid_build_101 = BuildInfo(master_name, builder_name, 101)
    valid_build_102 = BuildInfo(master_name, builder_name, 102)
    valid_build_102.commit_position = 1020

    mocked_get_build_info.side_effect = [
        (mock.ANY, invalid_build_100),
        (mock.ANY, invalid_build_101),
        (mock.ANY, valid_build_102),
    ]

    self.assertEqual(
        valid_build_102,
        step_util.GetValidBuild(master_name, builder_name, 100, step_name, True,
                                2))

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetValidBuildSearchAscendingOutOfRange(self, mocked_get_build_info):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'

    invalid_build_100 = BuildInfo(master_name, builder_name, 100)
    invalid_build_101 = BuildInfo(master_name, builder_name, 101)
    valid_build_102 = BuildInfo(master_name, builder_name, 102)
    valid_build_102.commit_position = 1020

    mocked_get_build_info.side_effect = [
        (mock.ANY, invalid_build_100),
        (mock.ANY, invalid_build_101),
        (mock.ANY, valid_build_102),
    ]

    self.assertIsNone(
        step_util.GetValidBuild(master_name, builder_name, 100, step_name, True,
                                1))

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetValidBuildSearchDescending(self, mocked_get_build_info):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'

    invalid_build_100 = BuildInfo(master_name, builder_name, 100)
    invalid_build_99 = BuildInfo(master_name, builder_name, 99)
    valid_build_98 = BuildInfo(master_name, builder_name, 98)
    valid_build_98.commit_position = 980

    mocked_get_build_info.side_effect = [
        (mock.ANY, invalid_build_100),
        (mock.ANY, invalid_build_99),
        (mock.ANY, valid_build_98),
    ]

    self.assertEqual(
        valid_build_98,
        step_util.GetValidBuild(master_name, builder_name, 100, step_name, True,
                                2))

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

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitRightAtUpperBound(self, *_):
    upper_bound_build_number = 4
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', None, upper_bound_build_number, 50)

    self.assertEqual(50, lower_bound.commit_position)
    self.assertEqual(50, upper_bound.commit_position)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitRightAtLowerBound(self, *_):
    upper_bound_build_number = 4
    lower_bound_build_number = 1
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', lower_bound_build_number, upper_bound_build_number, 20)

    self.assertEqual(20, lower_bound.commit_position)
    self.assertEqual(20, upper_bound.commit_position)

  def testIsStepSupportedByFinditObjectNone(self):
    self.assertFalse(step_util.IsStepSupportedByFindit(None, 'step', 'm'))

  def testIsStepSupportedByFinditOtherIsolatedScriptTest(self):
    self.assertFalse(
        step_util.IsStepSupportedByFindit(
            WebkitLayoutTestResults(None), 'telemetry_perf_tests', 'm'))

  @mock.patch.object(
      waterfall_config, 'StepIsSupportedForMaster', return_value=True)
  def testIsStepSupportedByFinditWebkitLayoutTests(self, _):
    self.assertTrue(
        step_util.IsStepSupportedByFindit(
            WebkitLayoutTestResults(None), 'webkit_layout_tests', 'm'))

  @mock.patch.object(
      waterfall_config, 'StepIsSupportedForMaster', return_value=True)
  def testIsStepSupportedByFinditGtests(self, _):
    self.assertTrue(
        step_util.IsStepSupportedByFindit(
            GtestTestResults(None), 'browser_tests', 'm'))
