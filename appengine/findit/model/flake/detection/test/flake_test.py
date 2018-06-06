# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase
from model.flake.detection.flake import Flake


class FlakeTest(TestCase):

  def testGetId(self):
    luci_project = 'chromium'
    step_name = 'step'
    test_name = 'test'
    self.assertEqual(
        'chromium/step/test',
        Flake.GetId(
            luci_project=luci_project, step_name=step_name,
            test_name=test_name))

  def testGet(self):
    luci_project = 'chromium'
    step_name = 'step'
    test_name = 'test'

    flake_id = 'chromium/step/test'
    flake = Flake(
        luci_project=luci_project,
        step_name=step_name,
        test_name=test_name,
        id=flake_id)
    flake.put()
    self.assertEqual(
        flake,
        Flake.Get(
            luci_project=luci_project, step_name=step_name,
            test_name=test_name))

  def testCreate(self):
    luci_project = 'chromium'
    step_name = 'step_name'
    test_name = 'test_name'

    flake = Flake.Create(
        luci_project=luci_project, step_name=step_name, test_name=test_name)
    flake.put()

    flakes = Flake.query(Flake.luci_project == luci_project,
                         Flake.step_name == step_name,
                         Flake.test_name == test_name).fetch()
    self.assertEqual(1, len(flakes))
    self.assertEqual(flake, flakes[0])

  def testComputedProperties(self):
    luci_project = 'chromium'
    step_name = 'test_target (with patch) on Android'
    test_name = 'instance/suite.PRE_PRE_test/1'

    flake = Flake.Create(
        luci_project=luci_project, step_name=step_name, test_name=test_name)
    flake.put()

    fetched_flake = Flake.Get(
        luci_project=luci_project, step_name=step_name, test_name=test_name)
    self.assertTrue(fetched_flake)
    self.assertEqual('test_target', fetched_flake.normalized_step_name)
    self.assertEqual('suite.test', fetched_flake.normalized_test_name)

  # Tests that for the normalized_step_name property, only ' (with patch)'
  # that appears as a postfix is stripped off.
  def testCreateFlakeHasWithPatchInStepName(self):
    luci_project = 'chromium'
    step_name = 'fake(withpatch)test_target (with patch) on Android'
    test_name = 'test_name'
    flake = Flake.Create(
        luci_project=luci_project, step_name=step_name, test_name=test_name)
    flake.put()

    fetched_flake = Flake.Get(
        luci_project=luci_project, step_name=step_name, test_name=test_name)
    self.assertTrue(fetched_flake)
    self.assertEqual('fake(withpatch)test_target',
                     fetched_flake.normalized_step_name)
