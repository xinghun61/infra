# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""App to access protected Google Storage URLs via their object names."""

import httplib
import logging
import urllib
import webapp2

import cloudstorage as gcs
from google.appengine.api import users


def google_login_required(fn):
  """Return 403 unless the user is logged in from a @google.com domain"""
  def wrapper(self, *args, **kwargs):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.uri))
    _, _, domain = user.email().partition('@')
    if domain == 'google.com':
      return fn(self, *args, **kwargs)
    logging.error('Unauthorized e-mail (%s)', user.user_id())
    self.response.out.write('Unauthorized e-mail')
    self.abort(httplib.FORBIDDEN)
  return wrapper


class ProxyPage(webapp2.RequestHandler):
  BLOCK_SIZE = 1024 * 1024 # 1MB at a time.
  RETRY_PARAMS = gcs.RetryParams(max_retries=3)

  @google_login_required
  def get(self, bucket, obj):
    gcs_path = '/%s/%s' % (bucket, urllib.quote(obj))
    logging.info('Opening %s using BLOCK_SIZE=%d', gcs_path, self.BLOCK_SIZE)
    try:
      gcs_file = gcs.open(gcs_path, retry_params=self.RETRY_PARAMS)
      gcs_stat = gcs.stat(gcs_path, retry_params=self.RETRY_PARAMS)
    except gcs.ForbiddenError:
      logging.exception("ForbiddenError accessing path %s", gcs_path)
      self.abort(httplib.FORBIDDEN)
    except gcs.AuthorizationError:
      logging.exception("AuthorizationError accessing path %s", gcs_path)
      self.abort(httplib.UNAUTHORIZED)

    self.response.headers["Content-Type"] = gcs_stat.content_type

    content_size = 0L
    block_num = 0
    while True:
      block = gcs_file.read(self.BLOCK_SIZE)
      if not block:
        break
      self.response.write(block)
      content_size += len(block)
      block_num += 1
    logging.info("Wrote content from [%s]: %s blocks, %s bytes",
                 gcs_path, block_num, content_size)


app = webapp2.WSGIApplication([
        ('/(.+)/(.*)', ProxyPage),
    ],)
