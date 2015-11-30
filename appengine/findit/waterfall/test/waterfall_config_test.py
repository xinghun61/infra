# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from model import wf_config
from waterfall import waterfall_config



class MastersTest(testing.AppengineTestCase):

  def setUp(self):
    super(MastersTest, self).setUp()

    class MockSettings():
      masters_to_blacklisted_steps = {
          'master1': ['step1', 'step2', 'step3'],
          'master2': ['step4', 'step5', 'step6']
      }
      builders_to_trybots = {
          'master1': {
              'builder1': {
                  'mastername': 'tryserver1',
                  'buildername': 'trybot1',
              }
          }
      }

    self.mock(wf_config, 'Settings', MockSettings)

  def testMasterIsSupported(self):
    self.assertTrue(waterfall_config.MasterIsSupported('master1'))
    self.assertFalse(waterfall_config.MasterIsSupported('blabla'))

  def testStepIsSupportedForMaster(self):
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('step1', 'master1'))
    self.assertTrue(
        waterfall_config.StepIsSupportedForMaster('step4', 'master1'))
    self.assertFalse(
        waterfall_config.StepIsSupportedForMaster('blabla', 'blabla'))

  def testGetTrybotForWaterfallBuilder(self):
    self.assertEqual(
        ('tryserver1', 'trybot1'),
        waterfall_config.GetTrybotForWaterfallBuilder('master1', 'builder1'))
    self.assertEqual(
        (None, None),
        waterfall_config.GetTrybotForWaterfallBuilder('master2', 'builder2'))
