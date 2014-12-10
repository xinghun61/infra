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
        properties={'builder_name': 'linux_rel'},
    )
    self.test_build.put()

  def test_is_available(self):
    self.assertTrue(self.test_build.is_available())
    tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    self.test_build.available_since = tomorrow
    self.assertFalse(self.test_build.is_available())

  def test_is_leasable(self):
    self.test_build.status = model.BuildStatus.SUCCESS
    self.assertFalse(self.test_build.is_leasable())

    self.test_build.status = model.BuildStatus.EXCEPTION
    self.assertFalse(self.test_build.is_leasable())

    self.test_build.status = model.BuildStatus.FAILURE
    self.assertFalse(self.test_build.is_leasable())

  def test_final_statuses(self):
    self.test_build.status = model.BuildStatus.SUCCESS
    self.assertTrue(self.test_build.is_status_final())

    self.test_build.status = model.BuildStatus.EXCEPTION
    self.assertTrue(self.test_build.is_status_final())

    self.test_build.status = model.BuildStatus.FAILURE
    self.assertTrue(self.test_build.is_status_final())

  def test_regenerate_lease_key(self):
    orig_lease_key = 0
    self.test_build.regenerate_lease_key()
    self.assertNotEqual(self.test_build.lease_key, orig_lease_key)
