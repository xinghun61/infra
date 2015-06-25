# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import urllib
import urllib2
import webapp2

from google.appengine.api import app_identity

import common


SKIP_HEADERS = [
    common.ENDPOINT_URL_HEADER,
    'Content_Length',
    'Content-Length',
    'Host',
    'User-Agent',
]


# Cannot use components.utils version here, because docker containers
# don't play well with non-local symlinks.
def _is_development_server():
  return os.environ.get('SERVER_SOFTWARE', '').startswith('Development')


class VMHandler(webapp2.RequestHandler):

  def requester_is_me(self):
    requester_id = self.request.headers.get('X-Appengine-Inbound-Appid')
    return requester_id == app_identity.get_application_id()

  def post(self):
    """Forwards the payload to specified endpoint, including headers.

    Expects endpoint url in a special header, and the correct OAuth
    Authorization header for the endpoint.
    """
    authorized = (
        self.requester_is_me() or _is_development_server())
    if not authorized:
      self.abort(403)
    url = self.request.headers.get(common.ENDPOINT_URL_HEADER)
    logging.debug('vm_module.post(%s)', url)
    if not url:
      logging.error('vm_module.post: no url specified.')
      self.abort(500)
    # Copy all the headers except X-* Google headers and a few special ones.
    headers = {
        k: v for k, v in self.request.headers.iteritems()
        if not k.startswith('X-') and k not in SKIP_HEADERS
    }
    logging.debug('Sending (synchronously) the payload to %s.', url)
    logging.debug('Headers:\n%s', '\n'.join(
        '  %s: %s' % (k, v) for k, v in headers.iteritems()))
    request = urllib2.Request(url, self.request.body, headers)
    urllib2.urlopen(request)
    logging.debug('Done sending the payload.')


logging.basicConfig(level=logging.DEBUG)
app = webapp2.WSGIApplication([
    (r'/vm.*', VMHandler),
    ], debug=True)
