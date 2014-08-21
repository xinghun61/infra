# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from google.appengine.api import users

from admin import clear_stats, set_bot_password

commands = {
  'clear-stats': clear_stats,
  'set-bot-password': set_bot_password,
}

class AdminDispatch(webapp2.RequestHandler): # pragma: no cover
  def get(self, command):
    if not users.is_current_user_admin():
      self.redirect(users.create_login_url(self.request.url))
      return
    commands[command].get(self)

  def post(self, command):
    if not users.is_current_user_admin():
      self.response.set_status(403)
      return
    self.response.headers.add_header('Content-Type', 'text/plain')
    commands[command].post(self)
