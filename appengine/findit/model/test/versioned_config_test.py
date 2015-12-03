# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from testing_utils import testing

from model.versioned_config import VersionedConfig


class _Config(VersionedConfig):
  a = ndb.IntegerProperty(indexed=False, default=0)


class VersionedConfigTest(testing.AppengineTestCase):
  def _CreateFirstVersion(self):
    config = _Config.Get()
    config.Update(a=1)

  def testGetWhenNoConfigCreatedYet(self):
    config = _Config.Get()
    self.assertIsNotNone(config)
    self.assertEqual(0, config.a)

  def testNonAdminCanNotUpdate(self):
    config = _Config.Get()
    with self.assertRaises(Exception):
      config.Update()

  def testUpdateWhenChanged(self):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    self._CreateFirstVersion()
    config = _Config.Get()
    self.assertIsNotNone(config)
    self.assertTrue(config.Update(a=2))

    config = _Config.Get()
    self.assertIsNotNone(config)
    self.assertEqual(2, config.version)
    self.assertEqual(2, config.a)

  def testNotUpdateWhenNotChanged(self):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    self._CreateFirstVersion()
    config = _Config.Get()
    self.assertIsNotNone(config)
    self.assertFalse(config.Update(a=1))

    config = _Config.Get()
    self.assertIsNotNone(config)
    self.assertEqual(1, config.version)
    self.assertEqual(1, config.a)
