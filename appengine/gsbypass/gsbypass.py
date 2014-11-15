# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""App to access protected Google Storage URLs via their object names."""

import cloudstorage as gcs
import logging
import re
import webapp2

from google.appengine.api import users


def google_login_required(fn):
  """Return 403 unless the user is logged in from a @google.com domain"""
  def wrapper(self, *args, **kwargs):
    user = users.get_current_user()
    _, _, domain = user.email().partition('@')
    if domain == 'google.com':
      return fn(self, *args, **kwargs)
    self.error(403)  # Unrecognized email or unauthroized domain.
    self.response.out.write('unauthroized email %s' % user.user_id())
  return wrapper


class ProxyPage(webapp2.RequestHandler):
  @google_login_required
  def get(self, bucket, obj):
    gcs_file = gcs.open('/%s/%s' % (bucket, obj))
    gcs_stat = gcs.stat('/%s/%s' % (bucket, obj))
    logging.info('Opening /%s/%s' % (bucket, obj))
    self.response.headers["Content-Type"] = gcs_stat.content_type
    while True:
      block = gcs_file.read(16 * 1024)
      if not block:
        return
      self.response.write(block)


app = webapp2.WSGIApplication([
        ('/(.+)/(.*)', ProxyPage),
    ],)
