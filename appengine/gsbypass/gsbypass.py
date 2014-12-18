# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""App to access protected Google Storage URLs via their object names."""

import cloudstorage as gcs
import logging
import webapp2

from google.appengine.api import users


def google_login_required(fn):
  """Return 403 unless the user is logged in from a @google.com domain"""
  def wrapper(self, *args, **kwargs):
    user = users.get_current_user()
    _, _, domain = user.email().partition('@')
    if domain == 'google.com':
      return fn(self, *args, **kwargs)
    self.error(403)  # Unrecognized email or unauthorized domain.
    self.response.out.write('unauthorized email %s' % user.user_id())
  return wrapper


class ProxyPage(webapp2.RequestHandler):
  @google_login_required
  def get(self, bucket, obj):
    BLOCK_SIZE = 16 * 1024
    filename = '/%s/%s' % (bucket, obj)
    gcs_file = gcs.open(filename)
    gcs_stat = gcs.stat(filename)
    logging.info('Opening %s using BLOCK_SIZE=%d' % (filename, BLOCK_SIZE))
    self.response.headers["Content-Type"] = gcs_stat.content_type

    block_num = 0
    while True:
      block = gcs_file.read(BLOCK_SIZE)
      if not block:
        logging.info('Finished reading %d blocks' % block_num)
        return
      block_num += 1
      self.response.write(block)


app = webapp2.WSGIApplication([
        ('/(.+)/(.*)', ProxyPage),
    ],)
