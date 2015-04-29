# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import app_identity
from google.appengine.ext.webapp import template
import os
import webapp2
import urllib

from google.appengine.api import urlfetch


# In development mode, use the un-vulcanized templates:
main_file = ('sheriff-o-matic.html' if
    os.environ['SERVER_SOFTWARE'].startswith("Development")
    else 'gen/index.html')
path = os.path.join(os.path.dirname(__file__), main_file)

f = open(path, 'rb')
main = f.read()
f.close()

class MainPage(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Strict-Transport-Security'] = (
        'max-age=10886400; includeSubDomains')
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write(main)

# This reverse-proxy exists in order to work around a same-origin policy
# that prevents JS served from SoM from fetching resources from
# chromium-build.appspot.com.
class Rotations(webapp2.RequestHandler):
  def get(self):
    result = urlfetch.fetch(
       url='https://chromium-build.appspot.com/p/chromium/all_rotations.js')
    self.response.out.write(result.content)

app = webapp2.WSGIApplication([
    ('/rotations', Rotations),
    ('/.*', MainPage),
], debug=True)

