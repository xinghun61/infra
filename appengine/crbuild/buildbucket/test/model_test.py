# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from test import CrBuildTestCase
from buildbucket import model


class BuildTest(CrBuildTestCase):
  def setUp(self):
    super(BuildTest, self).setUp()
    self.test_build = model.Build(
        namespace='chromium',
        status=model.BuildStatus.SCHEDULED,
        properties={'builder_name': 'linux_rel'},
    )
    self.test_build.put()

  def test_scheduled_is_leasable(self):
    self.assertTrue(self.test_build.is_leasable())

  def test_complete_build_is_not_leasable(self):
    self.test_build.status = model.BuildStatus.COMPLETE
    self.assertFalse(self.test_build.is_leasable())

  def test_unavailable_build_is_not_leasable(self):
    tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    self.test_build.available_since = tomorrow
    self.assertFalse(self.test_build.is_leasable())

  def test_regenerate_lease_key(self):
    orig_lease_key = 0
    self.test_build.regenerate_lease_key()
    self.assertNotEqual(self.test_build.lease_key, orig_lease_key)
