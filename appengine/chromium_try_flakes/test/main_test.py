# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

import main
from testing_utils import testing


class MainTestCase(testing.AppengineTestCase):
  app_module = main.app

  @mock.patch('google.appengine.api.app_identity.get_application_id')
  def test_logging_disabled_on_staging(self, get_app_id_mock):
    get_app_id_mock.return_value = 'chromium-try-flakes-staging'
    self.assertFalse(main.is_monitoring_enabled())

  @mock.patch('google.appengine.api.app_identity.get_application_id')
  def test_logging_enabled_on_prod(self, get_app_id_mock):
    get_app_id_mock.return_value = 'chromium-try-flakes'
    self.assertTrue(main.is_monitoring_enabled())
