# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# test_env should be loaded before any other app module.
from . import test_env

from testing_utils import testing

from components import utils
from components import auth_testing

import config


class TestConfig(testing.AppengineTestCase):
  def setUp(self):
    super(TestConfig, self).setUp()
    utils.clear_cache(config.config)

  def test_bootstrap(self):
    # Missing initially
    self.assertIsNone(config.GlobalConfig.fetch())
    # Bootstrap it.
    self.assertIsNotNone(config.config())
    # Now present.
    self.assertIsNotNone(config.GlobalConfig.fetch())

  def test_modify_empty(self):
    c = config.GlobalConfig()
    self.assertFalse(c.modify())

  def test_modify_noop(self):
    c = config.GlobalConfig()
    c.cas_gs_temp = '/bucket/stuff'
    self.assertFalse(c.modify(cas_gs_temp='/bucket/stuff'))

  def test_modify_for_real(self):
    auth_testing.mock_get_current_identity(self)
    c = config.GlobalConfig()
    c.cas_gs_temp = '/bucket/stuff'
    self.assertTrue(c.modify(cas_gs_temp='/bucket/other-stuff'))
    fetched = config.GlobalConfig.fetch()
    self.assertEqual(fetched.cas_gs_temp, '/bucket/other-stuff')
    self.assertEqual(fetched.updated_by, auth_testing.DEFAULT_MOCKED_IDENTITY)

  def test_warmup(self):
    # Just for code coverage.
    config.warmup()
