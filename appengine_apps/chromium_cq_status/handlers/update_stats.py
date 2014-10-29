# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from shared.utils import cronjob
from stats.analysis import analyze_interval

class UpdateStats(webapp2.RequestHandler): # pragma: no cover
  @cronjob
  def get(self):
    analyze_interval(int(self.request.get('interval_minutes')))
