# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from appengine_module.trooper_o_matic import alerts
from appengine_module.trooper_o_matic import build_details
from appengine_module.trooper_o_matic import cq
from appengine_module.trooper_o_matic import cron
from appengine_module.trooper_o_matic import tree
from appengine_module.trooper_o_matic import tree_status

# Set route definitions and enable debug stacks in the UI. See
# https://webapp-improved.appspot.com/guide/app.html#debug-flag
application = webapp2.WSGIApplication([
    ('[/]', alerts.OverviewHandler),
    ('/alerts', alerts.AlertsHandler),
    ('/build-details/(.*)', build_details.BuildDetailsHandler),
    ('/check-cq', cron.CheckCQHandler),
    ('/check-tree/(.*)', cron.CheckTreeHandler),
    ('/check-tree-status/([^/]*)/(.*)', cron.CheckTreeStatusHandler),
    ('/cq/(.*)', cq.CQHandler),
    ('/tree/(.*)', tree.TreeHandler),
    ('/tree-status/(.*)', tree_status.TreeStatusHandler),
    ('/project/([^/]*)/cq-length/?', cq.CQLengthJSONHandler),
    ('/project/([^/]*)/tree-status/?', tree_status.TreeStatusJSONHandler),
], debug=True)
