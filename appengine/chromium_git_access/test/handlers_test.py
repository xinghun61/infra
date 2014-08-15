# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Hack sys.path.
import setup_test_env  # pylint: disable=W0611

import webapp2

from appengine.utils import testing
from appengine.chromium_git_access import handlers


class TestHandlers(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(handlers.get_routes(), debug=True)

  def test_main_page(self):
    """Test that the root page renders."""
    response = self.test_app.get('/')
    self.assertEquals(response.status_int, 200)

  def test_warmup(self):
    """Test that warmup works."""
    response = self.test_app.get('/_ah/warmup')
    self.assertEquals(response.status_int, 200)
