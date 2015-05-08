# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import endpoints
import webapp2

from findit_api import FindItApi
from handlers import build_failure
from handlers import failure_log
from handlers import list_analyses
from handlers import monitor_alerts
from handlers import triage_analysis
from handlers import verify_analysis


handler_mappings = [
    ('/build-failure', build_failure.BuildFailure),
    ('/failure-log', failure_log.FailureLog),
    ('/list-analyses', list_analyses.ListAnalyses),
    ('/monitor-alerts', monitor_alerts.MonitorAlerts),
    ('/triage-analysis', triage_analysis.TriageAnalysis),
    ('/verify-analysis', verify_analysis.VerifyAnalysis),
]


# This is for Web pages.
web_application = webapp2.WSGIApplication(handler_mappings, debug=False)


# This is for Cloud Endpoint apis.
api_application = endpoints.api_server([FindItApi])
