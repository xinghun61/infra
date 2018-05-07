# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from dto.swarming_task_error import SwarmingTaskError
from services.flake_failure import pass_rate_util
from waterfall.flake import flake_constants
from waterfall.test.wf_testcase import WaterfallTestCase


class PassRateUtilTest(WaterfallTestCase):

  def testCalculateNewPassRate(self):
    self.assertEqual(0.75, pass_rate_util.CalculateNewPassRate(
        1.0, 10, 0.5, 10))

  def testGetPassRateNonexistentTest(self):
    swarming_task_output = FlakeSwarmingTaskOutput(
        error=None,
        iterations=0,
        pass_count=0,
        started_time=None,
        completed_time=None,
        task_id='task_id')
    self.assertEqual(flake_constants.PASS_RATE_TEST_NOT_FOUND,
                     pass_rate_util.GetPassRate(swarming_task_output))

  def testGetPassRate(self):
    swarming_task_output = FlakeSwarmingTaskOutput(
        error=None,
        iterations=10,
        pass_count=4,
        started_time=None,
        completed_time=None,
        task_id='task_id')
    self.assertEqual(0.4, pass_rate_util.GetPassRate(swarming_task_output))

  def testHasPassRateConverged(self):
    self.assertFalse(
        pass_rate_util.HasPassRateConverged(0, None, 0.5, 50, margin=0.01))
    self.assertTrue(
        pass_rate_util.HasPassRateConverged(0.5, 100, 0.5, 50, margin=0.01))
    self.assertFalse(
        pass_rate_util.HasPassRateConverged(0.5, 100, 1.0, 50, margin=0.01))
    self.assertTrue(
        pass_rate_util.HasPassRateConverged(0.5, 100, 1.0, 50, margin=0.5))

  def testHasSSufficientInformationNoPassRate(self):
    self.assertFalse(pass_rate_util.HasSufficientInformation(None, 0, 0, 0))

  def testHasSSufficientInformationEarlyFlakyInsufficientIterations(self):
    self.assertFalse(pass_rate_util.HasSufficientInformation(0.5, 2, 0.5, 2))

  def testHasSSufficientInformationEarlyFlaky(self):
    self.assertTrue(pass_rate_util.HasSufficientInformation(0.5, 20, 0.5, 20))

  def testHasSufficientInformationFlaky(self):
    self.assertTrue(pass_rate_util.HasSufficientInformation(0.5, 100, 0.5, 30))

  def testHasSufficientInformationEarlyStable(self):
    self.assertFalse(pass_rate_util.HasSufficientInformation(0.0, 3, 0.0, 3))
    self.assertFalse(pass_rate_util.HasSufficientInformation(1.0, 3, 1.0, 3))

  @mock.patch.object(
      pass_rate_util, 'MinimumIterationsReached', return_value=True)
  @mock.patch.object(pass_rate_util, 'HasPassRateConverged', return_value=False)
  def testHasSufficientInformationStable(self, *_):
    self.assertFalse(
        pass_rate_util.HasSufficientInformation(1.0, 100, 0.97, 30))

  def testIsFullyStable(self):
    self.assertTrue(pass_rate_util.IsFullyStable(-1))
    self.assertTrue(pass_rate_util.IsFullyStable(0.0))
    self.assertTrue(pass_rate_util.IsFullyStable(1.0))
    self.assertFalse(pass_rate_util.IsFullyStable(0.01))
    self.assertFalse(pass_rate_util.IsFullyStable(0.99))

  def testIsStable(self):
    self.assertTrue(pass_rate_util.IsStable(-1, 0.02, 0.98))
    self.assertTrue(pass_rate_util.IsStable(0.0, 0.02, 0.98))
    self.assertTrue(pass_rate_util.IsStable(0.02, 0.02, 0.98))
    self.assertTrue(pass_rate_util.IsStable(0.98, 0.02, 0.98))
    self.assertTrue(pass_rate_util.IsStable(1.0, 0.02, 0.98))
    self.assertFalse(pass_rate_util.IsStable(0.5, 0.02, 0.98))

  def testIsStableDefaultTresholds(self):
    self.assertTrue(pass_rate_util.IsStableDefaultThresholds(-1))
    self.assertTrue(pass_rate_util.IsStableDefaultThresholds(0.0))
    self.assertTrue(pass_rate_util.IsStableDefaultThresholds(0.02))
    self.assertTrue(pass_rate_util.IsStableDefaultThresholds(0.98))
    self.assertTrue(pass_rate_util.IsStableDefaultThresholds(1.0))
    self.assertFalse(pass_rate_util.IsStableDefaultThresholds(0.5))

  def testMinimumIterationsReached(self):
    self.assertTrue(
        pass_rate_util.MinimumIterationsReached(
            flake_constants.MINIMUM_ITERATIONS_REQUIRED_FOR_CONVERGENCE))
    self.assertFalse(pass_rate_util.MinimumIterationsReached(0))

  def testTestDoesNotExist(self):
    self.assertTrue(
        pass_rate_util.TestDoesNotExist(
            flake_constants.PASS_RATE_TEST_NOT_FOUND))
    self.assertFalse(pass_rate_util.TestDoesNotExist(0))
    self.assertFalse(pass_rate_util.TestDoesNotExist(1.0))
    self.assertFalse(pass_rate_util.TestDoesNotExist(0.5))
    self.assertFalse(pass_rate_util.TestDoesNotExist(None))
