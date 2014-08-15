# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from components import auth


def get_routes():
  return [
    webapp2.Route(r'/', MainHandler),
    webapp2.Route(r'/_ah/warmup', WarmupHandler),
  ]


class MainHandler(webapp2.RequestHandler):
  def get(self):
    self.response.write('Nothing to see here')


class WarmupHandler(webapp2.RequestHandler):
  def get(self):
    auth.warmup()
    self.response.write('ok')
