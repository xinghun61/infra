# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""AppEngine scripts to manage the chromium tree status.

   Logged in people with a @chromium.org email can change the status that
   appears on the waterfall page. The previous status are kept in the
   database and the last 100 topics.
"""

# Needs to be first to setup django, even if the import is unused.
# pylint: disable=W0611
import appengine_config

# Now safe to import other modules.
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

import base_page
import breakpad
import commit_queue
import event_push
import lkgr
import login
import profiling
import static_blobs_inline as static_blobs
import status
import utils
import xmpp


# Application configuration.
URLS = [
  ('/', status.MainPage),
  ('/([^/]+\.(?:gif|png|jpg|ico))', static_blobs.ServeHandler),
  ('/_ah/xmpp/message/chat/', xmpp.XMPPHandler),
  ('/allstatus/?', status.AllStatusPage),
  ('/breakpad/?', breakpad.BreakPad),
  ('/cq/receiver/?', commit_queue.Receiver),
  ('/cq/?', commit_queue.Summary),
  ('/cq/([^/]+)/?', commit_queue.User),
  ('/cq/([^/]+)/(\d+)/?', commit_queue.Issue),
  ('/cq/([^/]+)/(\d+)/(\d+)/?', commit_queue.Issue),
  ('/current/?', status.CurrentPage),
  ('/lkgr/?', lkgr.LastKnownGoodRevision),
  ('/login/?', login.Login),
  ('/profiling/?', profiling.Profiling),
  ('/recent-events/?', event_push.RecentEvents),
  ('/restricted/breakpad/cleanup/?', breakpad.Cleanup),
  ('/restricted/breakpad/im/?', breakpad.SendIM),
  ('/restricted/profiling/cleanup/?', profiling.Cleanup),
  ('/restricted/static_blobs/upload/(.*)/?', static_blobs.FormPage),
  ('/restricted/static_blobs/upload_internal/(.*)/?',
    static_blobs.UploadHandler),
  ('/restricted/status-processor/?', event_push.StatusProcessor),
  ('/revisions/?', lkgr.Revisions),
  ('/static_blobs/(.*)/?', static_blobs.ServeHandler),
  ('/static_blobs/list/?', static_blobs.ListPage),
  ('/status/?', status.StatusPage),
  ('/status-receiver/?', event_push.StatusReceiver),
  ('/status_viewer/?', status.StatusViewerPage),
]
APPLICATION = webapp.WSGIApplication(URLS, debug=True)


def main():
  """Manages and displays chromium tree and revisions status."""
  util.run_wsgi_app(APPLICATION)


if __name__ == "__main__":
  # Do some one-time initializations.
  base_page.bootstrap()
  breakpad.bootstrap()
  lkgr.bootstrap()
  status.bootstrap()
  utils.bootstrap()
  main()
