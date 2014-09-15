# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

import webapp2

class PostComment(webapp2.RequestHandler):
  def post(self):
    key = self.request.get('key')
    comment = self.request.get('comment')

    flake_key = ndb.Key(urlsafe=key)
    flake = flake_key.get()
    flake.comment = comment
    flake.put()
