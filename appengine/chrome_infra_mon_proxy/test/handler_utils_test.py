# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import webapp2

from testing_utils import testing

import common
import handler_utils
from components import auth

class TestHandler(handler_utils.BaseAuthHandler):
  @auth.public
  def get(self):
    self.render_response('main.html', title='Test')


class HandlerUtilsTest(testing.AppengineTestCase):
  _app = webapp2.WSGIApplication([(r'/', TestHandler)], debug=True)

  @property
  def app_module(self):
    return self._app

  def test_init_local_dev_server(self):
    """Smoke test for coverage."""
    self.mock(auth, 'bootstrap_group', lambda *_: None)
    handler_utils.init_local_dev_server()

  def test_base_handler(self):
    response = self.test_app.get('/')
    logging.info('response = %s', response)
    self.assertEquals(200, response.status_int)
