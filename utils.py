# Copyright (c) 2009 The Chromium Authors. All rights reserved.
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
  def decorated(myself, *args, **kwargs):
    if ('X-AppEngine-Cron' in myself.request.headers or
        'X-AppEngine-TaskName' in myself.request.headers or
        is_dev_env() or users.is_current_user_admin()):
      return func(myself, *args, **kwargs)
    elif users.get_current_user() is None:
      myself.redirect(users.create_login_url(myself.request.url))
    else:
      myself.response.set_status(401)
      myself.response.out.write('Handler only accessible for work queues')
  return decorated


def admin_only(func):
  """Valid for BasePage objects only."""
  def decorated(self, *args, **kwargs):
    if is_dev_env() or self.ValidateUser()[1]:
      return func(self, *args, **kwargs)
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Forbidden')
    self.error(403)
  return decorated


def AsDict(self):
  ret = {}
  for k in self.properties():
    ret[k] = str(getattr(self, k))
  return ret


def bootstrap():
  """Monkey patch db.Model.AsDict()"""
  db.Model.AsDict = AsDict
