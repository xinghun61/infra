# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.flake import Flake

import webapp2

class Search(webapp2.RequestHandler):
  def get(self):
    search = self.request.get('q')

    flake = Flake.query().filter(Flake.name == search).get()
    if not flake:
      self.response.write('No flake entry found for ' + search)
      return

    self.redirect('/all_flake_occurrences?key=%s' % flake.key.urlsafe())
