# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from model import wf_config
from waterfall import waterfall_config

MASTERS_TO_UNSUPPORTED_STEPS_DICT = {
    'master1': ['step1', 'step2', 'step3'],
    'master2': ['step4', 'step5', 'step6']
}


class MastersTest(testing.AppengineTestCase):

  def testMasterIsSupported(self):
    class MockSettings():
      masters_to_blacklisted_steps = MASTERS_TO_UNSUPPORTED_STEPS_DICT

    self.mock(wf_config, 'Settings', MockSettings)
    self.assertTrue(waterfall_config.MasterIsSupported('master1'))
    self.assertFalse(waterfall_config.MasterIsSupported('blabla'))

  def testStepIsSupportedForMaster(self):
    class MockSettings():
      masters_to_blacklisted_steps = MASTERS_TO_UNSUPPORTED_STEPS_DICT

    self.mock(wf_config, 'Settings', MockSettings)
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('step1', 'master1'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('step4', 'master1'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('blabla', 'blabla'))
