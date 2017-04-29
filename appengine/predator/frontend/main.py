# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from frontend.handlers import cracas_dashboard
from frontend.handlers import crash_config
from frontend.handlers import crash_handler
from frontend.handlers import cracas_result_feedback
from frontend.handlers import fracas_dashboard
from frontend.handlers import fracas_result_feedback
from frontend.handlers import triage_analysis
from frontend.handlers import update_component_config

frontend_web_pages_handler_mappings = [
    ('/config', crash_config.CrashConfig),
    ('/update-component-config',
     update_component_config.UpdateComponentConfig),
    ('/cracas-dashboard', cracas_dashboard.CracasDashBoard),
    ('/cracas-result-feedback',
     cracas_result_feedback.CracasResultFeedback),
    ('/fracas-dashboard', fracas_dashboard.FracasDashBoard),
    ('/fracas-result-feedback',
     fracas_result_feedback.FracasResultFeedback),
    ('/triage-analysis',
     triage_analysis.TriageAnalysis),
    ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
    ('/_ah/push-handlers/crash/cracas', crash_handler.CrashHandler),
    ('/_ah/push-handlers/crash/clusterfuzz', crash_handler.CrashHandler),
]
frontend_app = webapp2.WSGIApplication(
    frontend_web_pages_handler_mappings, debug=False)
