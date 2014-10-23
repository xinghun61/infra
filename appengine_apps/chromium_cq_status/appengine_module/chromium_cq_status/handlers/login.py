# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from google.appengine.api import users

class Login(webapp2.RequestHandler): # pragma: no cover
  def get(self):
    self.redirect(users.create_login_url())
