# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import gae_ts_mon

from frontend.handlers import clusterfuzz_dashboard
from frontend.handlers import clusterfuzz_result_feedback
from frontend.handlers import cracas_dashboard
from frontend.handlers import cracas_result_feedback
from frontend.handlers import crash_config
from frontend.handlers import crash_handler
from frontend.handlers import fracas_dashboard
from frontend.handlers import fracas_result_feedback
from frontend.handlers import triage_analysis
from frontend.handlers import uma_sampling_profiler_dashboard
from frontend.handlers import uma_sampling_profiler_result_feedback
from gae_libs.pipeline_wrapper import pipeline_status_ui


# App Engine pipeline status pages in the default module.
pipeline_status_handler_mappings = [
    ('/_ah/pipeline/rpc/tree', pipeline_status_ui._TreeStatusHandler),
    ('/_ah/pipeline/rpc/class_paths', pipeline_status_ui._ClassPathListHandler),
    ('/_ah/pipeline/rpc/list', pipeline_status_ui._RootListHandler),
    ('/_ah/pipeline(/.+)', pipeline_status_ui._StatusUiHandler),
]
pipeline_status_application = webapp2.WSGIApplication(
    pipeline_status_handler_mappings, debug=False)
gae_ts_mon.initialize(pipeline_status_application)


frontend_web_pages_handler_mappings = [
    ('/clusterfuzz/dashboard', clusterfuzz_dashboard.ClusterfuzzDashBoard),
    ('/clusterfuzz/result-feedback',
     clusterfuzz_result_feedback.ClusterfuzzResultFeedback),
    ('/config', crash_config.CrashConfig),
    ('/cracas/dashboard', cracas_dashboard.CracasDashBoard),
    ('/cracas/result-feedback',
     cracas_result_feedback.CracasResultFeedback),
    ('/uma-sampling-profiler/dashboard',
     uma_sampling_profiler_dashboard.UMASamplingProfilerDashboard),
    ('/uma-sampling-profiler/result-feedback',
     uma_sampling_profiler_result_feedback.UMASamplingProfilerResultFeedback),
    ('/fracas/dashboard', fracas_dashboard.FracasDashBoard),
    ('/fracas/result-feedback',
     fracas_result_feedback.FracasResultFeedback),
    ('/clusterfuzz/triage-analysis', triage_analysis.TriageAnalysis),
    ('/cracas/triage-analysis', triage_analysis.TriageAnalysis),
    ('/fracas/triage-analysis', triage_analysis.TriageAnalysis),
    ('/uma-sampling-profiler/triage-analysis', triage_analysis.TriageAnalysis),
    ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
    ('/_ah/push-handlers/crash/cracas', crash_handler.CrashHandler),
    ('/_ah/push-handlers/crash/clusterfuzz', crash_handler.CrashHandler),
    ('/_ah/push-handlers/regression/uma-sampling-profiler',
     crash_handler.CrashHandler),
]
frontend_app = webapp2.WSGIApplication(
    frontend_web_pages_handler_mappings, debug=False)
gae_ts_mon.initialize(frontend_app)
