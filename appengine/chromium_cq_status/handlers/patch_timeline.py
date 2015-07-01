# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2
import cgi

class PatchTimeline(webapp2.RequestHandler): # pragma: no cover
  def get(self, issue, patchset): # pylint: disable=W0221
    self.response.write(open('templates/trace_viewer.html').read() % {
      'issue': cgi.escape(issue, quote=True),
      'patchset': cgi.escape(patchset, quote=True),
    })
