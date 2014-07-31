# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import build_details
import cq
import cron
import tree

# Set route definitions and enable debug stacks in the UI. See
# https://webapp-improved.appspot.com/guide/app.html#debug-flag
application = webapp2.WSGIApplication([
    ('/build-details/(.*)', build_details.BuildDetailsHandler),
    ('/check-cq', cron.CheckCqHandler),
    ('/check-tree/(.*)', cron.CheckTreeHandler),
    ('/cq/(.*)', cq.CqHandler),
    ('/tree/(.*)', tree.TreeHandler),
], debug=True)
