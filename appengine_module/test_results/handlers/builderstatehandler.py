# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import webapp2

from datetime import datetime

from google.appengine.api import memcache

from appengine_module.test_results.model import builderstate


class GetBuilderState(webapp2.RequestHandler):
  """Return a list of masters mapped to their respective builders, annotated
  with when they last uploaded results."""

  def get(self):
    builder_state = memcache.get(builderstate.MEMCACHE_KEY)
    if not builder_state:
      builder_state = builderstate.BuilderState.refresh_all_data()
    if not builder_state:
      message = 'Builder data has not been generated.'
      logging.error(message)
      self.response.set_status(500)
      self.response.out.write(message)
      return

    write_response_start_time = datetime.now()
    self.response.headers['Content-Type'] = 'application/json'
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.out.write(builder_state)
    logging.info(
        'Writing response took %s',
        datetime.now() - write_response_start_time)


class Update(webapp2.RequestHandler):

  def get(self):
    if builderstate.BuilderState.refresh_all_data() is None:
      message = 'Builder data has not been generated.'
      logging.error(message)
      self.response.set_status(500)
      self.response.out.write(message)
      return

    self.response.set_status(200)
    self.response.out.write('ok')
