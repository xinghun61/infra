# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import webapp2

from testing_utils import testing

import common


class TestHandler(common.BaseHandler):
  def get(self):
    self.render_response('main.html', title='Test')


_app = webapp2.WSGIApplication([(r'/', TestHandler)], debug=True)


class CommonTest(testing.AppengineTestCase):

  @property
  def app_module(self):
    return _app

  def test_payload_stats(self):
    data = 'c00kedbeef'
    res = "type=<type 'str'>, 10 bytes, md5=407ab662183805731696989975459a9f"
    self.assertEquals(res, common.payload_stats(data))

  def test_base_handler(self):
    response = self.test_app.get('/')
    logging.info('response = %s', response)
    self.assertEquals(200, response.status_int)
