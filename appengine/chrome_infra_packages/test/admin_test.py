# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# test_env should be loaded before any other app module.
from . import test_env

from components import auth_testing

import frontend
import config


SERVICE_ACCOUNT_INFO = {
  'client_email': 'client@email.com',
  'private_key': 'private_key',
  'private_key_id': 'private_key_id',
}

GS_CONFIG = {
  'cas_gs_path': '/bucket/gs_path',
  'cas_gs_temp': '/bucket/gs_temp/',
}


class TestAdminHandlers(test_env.EndpointsApiTestCase):
  API_CLASS_NAME = 'AdminApi'

  def test_require_auth(self):
    auth_testing.mock_is_admin(self, False)
    with self.should_fail(403):
      self.call_api('service_account', SERVICE_ACCOUNT_INFO)
    with self.should_fail(403):
      self.call_api('gs_config', GS_CONFIG)

  def test_service_account(self):
    auth_testing.mock_is_admin(self, True)
    self.call_api('service_account', SERVICE_ACCOUNT_INFO)
    conf = config.GlobalConfig.fetch()
    self.assertEqual(conf.service_account_email, 'client@email.com')
    self.assertEqual(conf.service_account_pkey, 'private_key')
    self.assertEqual(conf.service_account_pkey_id, 'private_key_id')
    # Second call with same data doesn't change version.
    version = conf.key.id()
    self.call_api('service_account', SERVICE_ACCOUNT_INFO)
    self.assertEqual(config.GlobalConfig.fetch().key.id(), version)

  def test_gs_config_ok(self):
    auth_testing.mock_is_admin(self, True)
    self.call_api('gs_config', GS_CONFIG)
    conf = config.GlobalConfig.fetch()
    # Strips '/'.
    self.assertEqual(conf.cas_gs_path, '/bucket/gs_path')
    self.assertEqual(conf.cas_gs_temp, '/bucket/gs_temp')
    # Second call with same data doesn't change version.
    version = conf.key.id()
    self.call_api('gs_config', GS_CONFIG)
    self.assertEqual(config.GlobalConfig.fetch().key.id(), version)

  def test_gs_config_bad(self):
    auth_testing.mock_is_admin(self, True)
    with self.should_fail(400):
      self.call_api('gs_config', {
        'cas_gs_path': 'bucket/gs_path',
        'cas_gs_temp': '/bucket/gs_temp/'
      })
