# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utils."""

import os

from google.appengine.api import users
from google.appengine.ext import db


def is_dev_env():
  """Returns True if we're running in the development environment."""
  return 'Dev' in os.environ.get('SERVER_SOFTWARE', '')


def work_queue_only(func):
  """Decorator that only allows a request if from cron job, task, or an admin.

  Also allows access if running in development server environment.

  Args:
    func: A webapp.RequestHandler method.

  Returns:
    Function that will return a 401 error if not from an authorized source.
  """
  def decorated(self, *args, **kwargs):
    if ('X-AppEngine-Cron' in self.request.headers or
        'X-AppEngine-TaskName' in self.request.headers or
        self.is_admin):
      return func(self, *args, **kwargs)
    elif self.user is None:
      self.redirect(users.create_login_url(self.request.url))
    else:
      self.response.set_status(401)
      self.response.out.write('Handler only accessible for work queues')
  return decorated


def admin_only(func):
  """Valid for BasePage objects only."""
  def decorated(self, *args, **kwargs):
    if not self.user:
      self.redirect(users.create_login_url(self.request.url))
    elif self.is_admin:
      return func(self, *args, **kwargs)
    else:
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write('Forbidden')
      self.error(403)
  return decorated


def require_user(func):
  """A user must be logged in."""
  def decorated(self, *args, **kwargs):
    if not self.user:
      self.redirect(users.create_login_url(self.request.url))
    else:
      return func(self, *args, **kwargs)
  return decorated


def AsDict(self):
  ret = {}
  for k in self.properties():
    ret[k] = unicode(getattr(self, k))
  return ret


def bootstrap():
  """Monkey patch db.Model.AsDict()"""
  db.Model.AsDict = AsDict
