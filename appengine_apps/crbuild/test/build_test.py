# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from test import CrBuildTestCase
from model import Build, BuildProperties


class BuildTest(CrBuildTestCase):
  def setUp(self):
    super(BuildTest, self).setUp()
    self.test_build = Build(
        namespace='chromium',
        properties=BuildProperties(builder_name='linux_rel'),
    )
    self.test_build.put()

  def test_lease(self):
    leased_builds = Build.lease(10, 10, [self.test_build.namespace])
    self.assertEqual(len(leased_builds), 1)
    leased = leased_builds[0]
    self.assertEqual(leased, self.test_build)

    leased_builds = Build.lease(10, 10, [self.test_build.namespace])
    self.assertEqual(len(leased_builds), 0)

  def test_unlease(self):
    leased = Build.lease(10, 10, [self.test_build.namespace])
    self.test_build.unlease()
    leased = Build.lease(10, 10, [self.test_build.namespace])
    self.assertEqual(len(leased), 1)
    self.assertEqual(leased[0], self.test_build)
