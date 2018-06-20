# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase
from model.flake.detection.flake import Flake


class FlakeTest(TestCase):

  def testNormalizeStepName(self):
    self.assertEqual('test_target', Flake.NormalizeStepName('test_target'))

    self.assertEqual('test_target',
                     Flake.NormalizeStepName('test_target on Android'))

    self.assertEqual(
        'test_target',
        Flake.NormalizeStepName('test_target (with patch) on Android'))

    # Only '(with patch)' that appears as a postfix is stripped off.
    self.assertEqual(
        'fake(withpatch)test_target',
        Flake.NormalizeStepName(
            'fake(withpatch)test_target (with patch) on Android'))

  def testNormalizeTestName(self):
    self.assertEqual('suite.test', Flake.NormalizeTestName('suite.test'))

    self.assertEqual('suite.test', Flake.NormalizeTestName('a/suite.test/0'))

    self.assertEqual('suite.test',
                     Flake.NormalizeTestName('suite.PRE_PRE_test'))

    self.assertEqual('suite.test',
                     Flake.NormalizeTestName('a/suite.PRE_PRE_test/0'))

  def testGetId(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'normalized_test'
    self.assertEqual(
        'chromium@normalized_step@normalized_test',
        Flake.GetId(
            luci_project=luci_project,
            normalized_step_name=normalized_step_name,
            normalized_test_name=normalized_test_name))

  def testCreate(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'normalized_test'

    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)
    flake.put()

    fetched_flakes = Flake.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(flake, fetched_flakes[0])
