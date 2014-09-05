# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from google.appengine.api import users

from appengine_module.chromium_cq_status.stats.analysis import analyze_interval

def cronjob(cronjob_get):
  def checked_cronjob_get(self):
    assert (self.request.headers.get('X-AppEngine-Cron') or
        users.is_current_user_admin())
    cronjob_get(self)
  return checked_cronjob_get

class Login(webapp2.RequestHandler): # pragma: no cover
  def get(self):
    self.redirect(users.create_login_url())

class UpdateStats(webapp2.RequestHandler): # pragma: no cover
  @cronjob
  def get(self):
    analyze_interval(int(self.request.get('interval_days')))

app = webapp2.WSGIApplication([
    (r'/background/login', Login),
    (r'/background/update-stats', UpdateStats),
  ], debug=True)
