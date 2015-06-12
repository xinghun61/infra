# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import alerts
import internal_alerts
import webapp2

from google.appengine.api import users


class TimeSeriesInternalAlertsHandler(internal_alerts.InternalAlertsHandler):
  ALERT_TYPE = 'ts-internal-alerts'

class TimeSeriesAlertsHandler(alerts.AlertsHandler):
  ALERT_TYPE = 'ts-alerts'


app = webapp2.WSGIApplication([
    ('/ts-alerts', TimeSeriesAlertsHandler),
    ('/ts-internal-alerts', TimeSeriesInternalAlertsHandler)])
