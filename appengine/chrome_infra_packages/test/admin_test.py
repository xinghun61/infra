# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing
from components import auth_testing

import admin
import config


GS_CONFIG = {
  'cas_gs_path': '/bucket/gs_path',
  'cas_gs_temp': '/bucket/gs_temp/',
}


class TestAdminHandlers(testing.EndpointsTestCase):
  api_service_cls = admin.AdminApi

  def test_require_auth(self):
    auth_testing.mock_is_admin(self, False)
    with self.call_should_fail(403):
      self.call_api('gs_config', GS_CONFIG)

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
    with self.call_should_fail(400):
      self.call_api('gs_config', {
        'cas_gs_path': 'bucket/gs_path',
        'cas_gs_temp': '/bucket/gs_temp/'
      })
