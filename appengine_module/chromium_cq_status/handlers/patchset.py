# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

class Patchset(webapp2.RequestHandler): # pragma: no cover
  def get(self, issue, patchset): # pylint: disable-msg=W0221
    self.response.write(open('templates/patchset.html').read() % {
      'issue': issue,
      'patchset': patchset,
    })
