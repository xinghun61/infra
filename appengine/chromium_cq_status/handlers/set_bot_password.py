# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import users
from google.appengine.ext import webapp

from shared import utils
from shared.config import CQ_BOT_PASSWORD_KEY
from model.password import Password # pylint: disable-msg=E0611

class SetBotPassword(webapp.RequestHandler): # pragma: no cover
  def get(self):
    if not users.is_current_user_admin():
      self.redirect(users.create_login_url(self.request.url))
      return
    self.response.write(open('templates/set_bot_password.html').read())

  def post(self):
    if not users.is_current_user_admin():
      self.response.set_status(403)
      return

    password = self.request.get('password')
    if not password:
      self.response.write('"password" field missing.')
      return

    Password.get_or_insert(
        CQ_BOT_PASSWORD_KEY,
        sha1=utils.password_sha1(password)
    ).put()
