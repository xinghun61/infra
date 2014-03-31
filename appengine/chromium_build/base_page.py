# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os.path
import re

from google.appengine.api import memcache
from google.appengine.api import users
import webapp2
from google.appengine.ext.webapp import template


class BasePage(webapp2.RequestHandler):
  """Base request handler with this application specific helpers."""
  # Check if the username ends with @chromium.org/@google.com.
  _VALID_EMAIL = re.compile(r"^.+@(chromium\.org|google\.com)$")
  app_name = ''
  _is_admin = None
  _user = None
  _initialized = False

  def _late_init(self):
    """Initializes self._is_admin and self._user once the request object is
    setup.
    """
    self._is_admin = False

    self._user = users.get_current_user()
    if not self._is_admin and self._user:
      self._is_admin = bool(
          users.is_current_user_admin() or
          self._VALID_EMAIL.match(self._user.email()))
    self._initialized = True
    logging.info('Admin: %s, User: %s' % (self._is_admin, self._user))

  @property
  def is_admin(self):
    if not self._initialized:
      self._late_init()
    return self._is_admin

  @property
  def user(self):
    if not self._initialized:
      self._late_init()
    return self._user

  def InitializeTemplate(self, title='Chromium Build'):
    """Initializes the template values with information needed by all pages."""
    user_nickname = self.user.email() if self.user else ''
    template_values = {
      'app_name': self.app_name,
      'current_utc_time': datetime.datetime.now(),
      'is_admin': self.is_admin,
      'login_url': users.create_login_url(self.request.url),
      'logout_url': users.create_logout_url(self.request.url),
      'title': title,
      'user': self.user,
      'user_nickname': user_nickname,
    }
    return template_values

  def DisplayTemplate(self, name, template_values, use_cache=False):
    """Replies to a http request with a template.

    Optionally cache it for 1 second. Only to be used for user-invariant
    pages!
    """
    self.response.headers['Cache-Control'] =  'no-cache, private, max-age=0'
    buff = None
    if use_cache:
      buff = memcache.get(name)
    if not buff:
      path = os.path.join(os.path.dirname(__file__), 'templates/%s' % name)
      buff = template.render(path, template_values)
      if use_cache:
        memcache.add(name, buff, 1)
    self.response.out.write(buff)


def bootstrap():
  app_name = os.environ['APPLICATION_ID']
  BasePage.app_name = app_name
