# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utils."""

from google.appengine.api import users


def admin_only(func):
  """Valid for BasePage objects only."""
  def decorated(self, *args, **kwargs):
    if self.is_admin:
      return func(self, *args, **kwargs)
    else:
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write('Forbidden')
      self.error(403)
  return decorated


def clean_int(value, default):
  """Convert a value to an int, or the default value if conversion fails."""
  try:
    return int(value)
  except (TypeError, ValueError):
    return default


def require_user(func):
  """A user must be logged in."""
  def decorated(self, *args, **kwargs):
    if not self.user:
      self.redirect(users.create_login_url(self.request.url))
    else:
      return func(self, *args, **kwargs)
  return decorated
