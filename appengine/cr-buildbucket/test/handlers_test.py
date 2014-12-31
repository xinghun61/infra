# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
from testing_utils import testing

import acl
import handlers
import main
import service
import test


class HandlersTestCase(testing.AppengineTestCase):
  def test_create_service(self):
    self.assertTrue(
        isinstance(handlers.create_service(), service.BuildBucketService))


class BuildBucketBackendHandlersTest(testing.AppengineTestCase):
  @property
  def app_module(self):
    return main.create_backend_app()

  def setUp(self):
    super(BuildBucketBackendHandlersTest, self).setUp()
    self.service = mock.Mock()
    self.mock(handlers, 'create_service', lambda: self.service)

  def test_reset_expired_builds(self):
    path = '/internal/cron/buildbucket/reset_expired_builds'
    response = self.test_app.get(path, headers={'X-AppEngine-Cron': 'true'})
    self.assertEquals(200, response.status_int)
    self.service.reset_expired_builds.assert_called_once_with()
