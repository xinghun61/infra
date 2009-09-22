# Copyright (c) 2008-2009 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""AppEngine scripts to manage the chromium tree status.

   Logged in people with a @chromium.org email can change the status that
   appears on the waterfall page. The previous status are kept in the
   database and the last 100 topics.
"""

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

import lkgr
import status


# Application configuration.
URLS = [
  ('/', status.MainPage),
  ('/allstatus', status.AllStatusPage),
  ('/current', status.CurrentPage),
  ('/status', status.StatusPage),
  ('/revisions', lkgr.Revisions),
  ('/lkgr', lkgr.LastKnownGoodRevision)
]
APPLICATION = webapp.WSGIApplication(URLS, debug=True)


def main():
  """Manages and displays chromium tree and revisions status."""
  util.run_wsgi_app(APPLICATION)


if __name__ == "__main__":
  main()
