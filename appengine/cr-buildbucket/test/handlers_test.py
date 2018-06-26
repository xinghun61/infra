# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from testing_utils import testing
import main


class BuildBucketBackendHandlersTest(testing.AppengineTestCase):

  @property
  def app_module(self):
    return main.create_backend_app()

  @mock.patch('service.check_expired_builds', autospec=True)
  def test_check_expired_builds(self, check_expired_builds):
    path = '/internal/cron/buildbucket/check_expired_builds'
    response = self.test_app.get(path, headers={'X-AppEngine-Cron': 'true'})
    self.assertEquals(200, response.status_int)
    check_expired_builds.assert_called_once_with()
