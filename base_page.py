# Copyright (c) 2008-2009 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility base class."""

import datetime
import hashlib
import os
import re

from google.appengine.api import memcache
from google.appengine.api import oauth
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


class Passwords(db.Model):
  """Super users. Useful for automated scripts."""
  password_sha1 = db.StringProperty(required=True, multiline=False)


class GlobalConfig(db.Model):
  """Instance-specific config like application name."""
  app_name = db.StringProperty(required=True)


class BasePage(webapp.RequestHandler):
  """Utility functions needed to validate user and display a template."""
  _VALID_EMAIL = re.compile(r"^.*@(chromium\.org|google\.com)$")
  app_name = ''

  def __init__(self):
    webapp.RequestHandler.__init__(self)

  def GetCurrentUser(self):
    """Gets the current user (may be an OAuth user)."""
    user = users.get_current_user()
    if not user:
      try:
        user = oauth.get_current_user()
      except oauth.OAuthRequestError:
        return None
    return user

  def ValidateUser(self):
    """Checks if the user has the right to add messages.

    Returns tuple (validated, is_admin)"""
    # If the current user is not logged in, redirect to the login page.
    user = self.GetCurrentUser()
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

    # Check if the username ends with @chromium.org/@google.com.
    return (True, self._VALID_EMAIL.match(user.email()))

  def InitializeTemplate(self, title):
    """Initializes the template values with information needed by all pages."""
    user = self.GetCurrentUser()
    if user:
      user_email = user.email()
    else:
      user_email = ''
    template_values = {
      'app_name': self.app_name,
      'username': user_email,
      'title': title,
      'current_UTC_time': datetime.datetime.now(),
    }
    return template_values

  def DisplayTemplate(self, name, template_values, use_cache=False):
    """Replies to a http request with a template.

    Optionally cache it for 1 second. Only to be used for user-invariant
    pages!"""
    self.response.headers['Cache-Control'] =  'no-cache, private, max-age=0'
    buffer = None
    if use_cache:
      buffer = memcache.get(name)
    if not buffer:
      path = os.path.join(os.path.dirname(__file__), 'templates/%s' % name)
      buffer = template.render(path, template_values)
      if use_cache:
        memcache.add(name, buffer, 1)
    self.response.out.write(buffer)


def bootstrap():
  app_name = os.environ['APPLICATION_ID']
  if app_name.endswith('-status'):
    app_name = app_name[:-7]
  config = db.GqlQuery('SELECT * FROM GlobalConfig').get()
  if config is None:
    # Insert a dummy GlobalConfig so it can be edited through the admin
    # console
    GlobalConfig(app_name=app_name).put()
  elif not config.app_name:
    config.app_name = app_name
    config.put()
  else:
    app_name = config.app_name
  BasePage.app_name = app_name

  if db.GqlQuery('SELECT __key__ FROM Passwords').get() is None:
    # Insert a dummy Passwords so it can be edited through the admin console
    Passwords(password_sha1='invalidhash').put()
