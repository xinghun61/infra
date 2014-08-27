# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from google.appengine.api import users

from stats import analysis

commands = { # pragma: no cover
  'update-daily-stats': lambda: analysis.analyze_interval(days=1),
  'update-weekly-stats': lambda: analysis.analyze_interval(days=7),
}

class CronDispatch(webapp2.RequestHandler): # pragma: no cover
  def get(self, job): # pylint: disable-msg=W0221,R0201
    assert users.is_current_user_admin()
    commands[job]()
