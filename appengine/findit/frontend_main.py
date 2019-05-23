# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import gae_ts_mon

from gae_libs import appengine_util
from gae_libs.pipelines import pipeline_status_ui
from handlers import auto_revert_metrics
from handlers import build_failure
from handlers import check_duplicate_failures
from handlers import config
from handlers import culprit
from handlers import failure_log
from handlers import home
from handlers import list_analyses
from handlers import pipeline_errors_dashboard
from handlers import triage_suspected_cl
from handlers import trooper
from handlers import try_job_dashboard
from handlers import url_redirect
from handlers.flake import check_flake
from handlers.flake import flake_culprit
from handlers.flake import list_flakes
from handlers.flake import triage_flake_analysis
from handlers.flake.detection import rank_flakes
from handlers.flake.detection import show_flake
from handlers.flake.reporting import component_report
from handlers.flake.reporting import flake_report

# App Engine pipeline status pages.
pipeline_status_handler_mappings = [
    ('/_ah/pipeline/rpc/tree', pipeline_status_ui._TreeStatusHandler),
    ('/_ah/pipeline/rpc/class_paths', pipeline_status_ui._ClassPathListHandler),
    ('/_ah/pipeline/rpc/list', pipeline_status_ui._RootListHandler),
    ('/_ah/pipeline(/.+)', pipeline_status_ui._StatusUiHandler),
]
pipeline_status_application = webapp2.WSGIApplication(
    pipeline_status_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(pipeline_status_application)

# waterfall frontend.
waterfall_frontend_web_pages_handler_mappings = [
    ('/', home.Home),
    ('/waterfall/auto-revert-metrics', auto_revert_metrics.AutoRevertMetrics),
    ('/waterfall/check-duplicate-failures',
     check_duplicate_failures.CheckDuplicateFailures),
    ('/waterfall/config', config.Configuration),
    ('/waterfall/culprit', culprit.Culprit),
    ('/waterfall/failure', build_failure.BuildFailure),
    ('/waterfall/failure-log', failure_log.FailureLog),
    ('/waterfall/list-failures', list_analyses.ListAnalyses),
    ('/waterfall/pipeline-errors-dashboard',
     pipeline_errors_dashboard.PipelineErrorsDashboard),
    ('/waterfall/triage-suspected-cl', triage_suspected_cl.TriageSuspectedCl),
    ('/waterfall/trooper', trooper.Trooper),
    ('/waterfall/try-job-dashboard', try_job_dashboard.TryJobDashboard),
    (r'/.*', url_redirect.URLRedirect),
]
waterfall_frontend_web_application = webapp2.WSGIApplication(
    waterfall_frontend_web_pages_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(waterfall_frontend_web_application)

# Flake frontend.
flake_detection_frontend_web_pages_handler_mappings = [
    ('/p/chromium/flake-portal', rank_flakes.RankFlakes),
    ('/p/chromium/flake-portal/flakes', rank_flakes.RankFlakes),
    ('/p/chromium/flake-portal/flakes/occurrences', show_flake.ShowFlake),
    ('/p/chromium/flake-portal/analysis', list_flakes.ListFlakes),
    ('/p/chromium/flake-portal/analysis/analyze', check_flake.CheckFlake),
    ('/p/chromium/flake-portal/analysis/culprit', flake_culprit.FlakeCulprit),
    ('/p/chromium/flake-portal/analysis/triage',
     triage_flake_analysis.TriageFlakeAnalysis),
    ('/p/chromium/flake-portal/report', flake_report.FlakeReport),
    ('/p/chromium/flake-portal/report/component',
     component_report.ComponentReport),
    (r'/.*', url_redirect.URLRedirect),
]
flake_detection_frontend_web_application = webapp2.WSGIApplication(
    flake_detection_frontend_web_pages_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(flake_detection_frontend_web_application)
