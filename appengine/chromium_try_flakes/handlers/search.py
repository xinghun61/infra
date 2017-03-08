# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.flake import Flake
from test_results.util import normalize_test_type

import webapp2

class Search(webapp2.RequestHandler):
  def get(self):
    search = self.request.get('q')

    flake = Flake.query().filter(Flake.name == search).get()
    if flake:
      self.redirect('/all_flake_occurrences?key=%s' % flake.key.urlsafe())
      return

    # Users might search using full step name. Try normalizing it before
    # searching. Note that this won't find flakes in a step where
    # chromium-try-flakes was able to determine which test has failed. Instead,
    # users should search using the test name.
    normalized_step_name = normalize_test_type(search)
    flake = Flake.query().filter(Flake.name == normalized_step_name).get()
    if flake:
      self.redirect('/all_flake_occurrences?key=%s' % flake.key.urlsafe())
      return

    self.response.write('No flake entry found for ' + search)
