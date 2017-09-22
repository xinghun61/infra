# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""AppEngine scripts to manage the chromium tree status.

   Logged in people with a @chromium.org email can change the status that
   appears on the waterfall page. The previous status are kept in the
   database and the last 100 topics.
"""

from google.appengine.ext import webapp

from appengine_module.chromium_status import base_page
from appengine_module.chromium_status import breakpad
from appengine_module.chromium_status import event_push
from appengine_module.chromium_status import git_lkgr
from appengine_module.chromium_status import lkgr
from appengine_module.chromium_status import login
from appengine_module.chromium_status import profiling
from appengine_module.chromium_status import static_blobs_inline as static_blobs
from appengine_module.chromium_status import status
from appengine_module.chromium_status import utils
from appengine_module.chromium_status import xmpp


class Warmup(webapp.RequestHandler):
  def get(self):
    """This handler is called as the initial request to 'warmup' the process."""
    pass


# Application configuration.
URLS = [
  ('/', status.MainPage),
  ('/([^/]+\.(?:gif|png|jpg|ico))', static_blobs.ServeHandler),
  ('/_ah/warmup', Warmup),
  ('/allstatus/?', status.AllStatusPage),
  ('/current/?', status.CurrentPage),
  ('/lkgr/?', git_lkgr.LastKnownGoodRevisionGIT),
  ('/git-lkgr/?', git_lkgr.LastKnownGoodRevisionGIT),
  ('/login/?', login.Login),
  ('/revisions/?', git_lkgr.Commits),
  ('/commits/?', git_lkgr.Commits),
  ('/status/?', status.StatusPage),
  ('/status_viewer/?', status.StatusViewerPage),
]
APPLICATION = webapp.WSGIApplication(URLS, debug=True)


# Do some one-time initializations.
base_page.bootstrap()
breakpad.bootstrap()
lkgr.bootstrap()
git_lkgr.bootstrap()
status.bootstrap()
utils.bootstrap()
