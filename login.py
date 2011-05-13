# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Url handler to login a user."""

from google.appengine.api import users
from google.appengine.ext import webapp


class Login(webapp.RequestHandler):
  def get(self):
    self.response.set_status(403)
    self.response.out.write('Requires a POST request.')

  def post(self):
    """Redirects back to the referrer.

    If the referer is not present or not on the same server, return 403.
    """
    referer = self.request.headers.get('Referer')
    if referer and referer.startswith(self.request.host_url):
      self.redirect(users.create_login_url(referer))
    else:
      self.response.set_status(403)
      self.response.out.write(
          'the login request must come from the same server.')
