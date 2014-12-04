# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from test import CrBuildTestCase
from model import Build, BuildProperties, BuildStatus


class BuildTest(CrBuildTestCase):
  def setUp(self):
    super(BuildTest, self).setUp()
    self.test_build = Build(
        namespace='chromium',
        properties=BuildProperties(builder_name='linux_rel'),
    )
    self.test_build.put()

  def test_builder_name(self):
    self.assertEqual(self.test_build.builder_name, 'linux_rel')

  def test_status(self):
    self.assertEqual(self.test_build.status, BuildStatus.SCHEDULED)
    self.test_build.set_status(BuildStatus.SCHEDULED)
    self.test_build.set_status(BuildStatus.SUCCESS)
    self.assertEqual(self.test_build.status, BuildStatus.SUCCESS)

  def test_lease(self):
    leased_builds = Build.lease([self.test_build.namespace])
    self.assertEqual(len(leased_builds), 1)
    leased = leased_builds[0]
    self.assertEqual(leased, self.test_build)

    leased_builds = Build.lease([self.test_build.namespace])
    self.assertEqual(len(leased_builds), 0)

  def test_lease_for_day(self):
    with self.assertRaises(AssertionError):
      Build.lease([self.test_build.namespace], lease_seconds=24 * 60 * 60)

  def test_lease_1000_builds(self):
    with self.assertRaises(AssertionError):
      Build.lease([self.test_build.namespace], max_builds=1000)

  def test_modify_lease(self):
    self.test_build.modify_lease(0)
    self.assertTrue(self.test_build.is_available())

  def test_cannot_lease_completed_build(self):
    self.test_build.status = BuildStatus.SUCCESS
    self.test_build.put()
    self.assertFalse(Build.lease([self.test_build.namespace]))

  def test_cannot_lease_unavailable_build(self):
    self.assertTrue(Build.lease([self.test_build.namespace]))
    self.assertFalse(Build.lease([self.test_build.namespace]))

  def test_unlease(self):
    leased = Build.lease([self.test_build.namespace])
    self.test_build.unlease()
    leased = Build.lease([self.test_build.namespace])
    self.assertEqual(len(leased), 1)
    self.assertEqual(leased[0], self.test_build)
