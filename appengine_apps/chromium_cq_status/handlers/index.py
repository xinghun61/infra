# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import users
import webapp2

from shared import utils

class Index(webapp2.RequestHandler): # pragma: no cover
  def get(self):
    self.response.write(open('templates/index.html').read() % {
      'login_url': users.create_login_url(),
      'valid_user': bool(utils.is_valid_user()),
    })
