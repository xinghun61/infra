# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from services.flake_failure import pass_rate_util
from waterfall.flake import flake_constants
from waterfall.test.wf_testcase import WaterfallTestCase


class PassRateUtilTest(WaterfallTestCase):

  def testArePassRatesEqual(self):
    self.assertTrue(pass_rate_util.ArePassRatesEqual(0.1, 0.1))
    self.assertTrue(pass_rate_util.ArePassRatesEqual(-1, -1))
    self.assertFalse(pass_rate_util.ArePassRatesEqual(1.0, 0.0))

  def testHasPassRateConverged(self):
    self.assertFalse(
        pass_rate_util.HasPassRateConverged(0, None, 0.5, 50, margin=0.01))
    self.assertTrue(
        pass_rate_util.HasPassRateConverged(0.5, 100, 0.5, 50, margin=0.01))
    self.assertFalse(
        pass_rate_util.HasPassRateConverged(0.5, 100, 1.0, 50, margin=0.01))
    self.assertTrue(
        pass_rate_util.HasPassRateConverged(0.5, 100, 1.0, 50, margin=0.5))

  @mock.patch.object(
      pass_rate_util, 'MinimumIterationsReached', return_value=True)
  @mock.patch.object(pass_rate_util, 'HasPassRateConverged', return_value=True)
  def testHasSufficientInformationForConvergence(self, *_):
    self.assertTrue(
        pass_rate_util.HasSufficientInformationForConvergence(
            0.5, 100, 0.5, 30))

  def testIsFullyStable(self):
    self.assertTrue(pass_rate_util.IsFullyStable(-1))
    self.assertTrue(pass_rate_util.IsFullyStable(0.0))
    self.assertTrue(pass_rate_util.IsFullyStable(1.0))
    self.assertFalse(pass_rate_util.IsFullyStable(0.01))
    self.assertFalse(pass_rate_util.IsFullyStable(0.99))

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
