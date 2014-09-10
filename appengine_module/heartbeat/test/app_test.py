# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from appengine_module.testing_utils import testing
from appengine_module.heartbeat import app


class RequestHandlerTest(testing.AppengineTestCase):
  """Unit tests for app.RequestHandler."""
  app_module = app.app

  def test_get(self):
    """Tests that RequestHandler can serve GET requests."""
    response = self.test_app.get('/')
    self.assertEquals(200, response.status_code)
