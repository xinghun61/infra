# Copyright (c) 2008-2009 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility base class."""

import datetime
import hashlib
import os
import re

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


class Passwords(db.Model):
  """Super users. Useful for automated scripts."""
  password_sha1 = db.StringProperty(required=True, multiline=False)


class BasePage(webapp.RequestHandler):
  """Utility functions needed to validate user and display a template."""
  _VALID_EMAIL = re.compile(r"^.*@chromium\.org$")

  def ValidateUser(self):
    """Checks if the user has the right to add messages.

    Returns tuple (validated, is_admin)"""
    # If the current user is not logged in, redirect to the login page.
    user = users.get_current_user()
    if not user:
      # Warning: this is not secure over http, use https.
      password = self.request.get('password')
      if password:
        sha1_pass = hashlib.sha1(password).hexdigest()
        if Passwords.gql('WHERE password_sha1 = :1', sha1_pass).get():
          # The password is valid, this is a super admin.
          return (True, True)
      self.redirect(users.create_login_url(self.request.uri))
      return (False, False)

    # Check if the username ends with @chromium.org.
    return (True, self._VALID_EMAIL.match(user.email()))

  def InitializeTemplate(self, title):
    """Initializes the template values with information needed by all pages."""
    user = users.get_current_user()
    template_values = {
      'username': user.email(),
      'title': title,
      'current_UTC_time': datetime.datetime.now(),
    }
    return template_values

  def DisplayTemplate(self, name, template_values):
    path = os.path.join(os.path.dirname(__file__), 'templates/%s' % name)
    self.response.headers['Cache-Control'] =  'no-cache, private, max-age=0'
    self.response.out.write(template.render(path, template_values))
