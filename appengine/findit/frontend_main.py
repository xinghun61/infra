# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import gae_ts_mon

from gae_libs import appengine_util
from gae_libs.pipelines import pipeline_handlers
from gae_libs.pipelines import pipeline_status_ui
from handlers import auto_revert_metrics
from handlers import build_ahead
from handlers import build_failure
from handlers import calculate_confidence_scores
from handlers import change_auto_revert_setting
from handlers import check_duplicate_failures
from handlers import check_reverted_cls
from handlers import check_trybot_mapping
from handlers import collect_tree_closures
from handlers import completed_build_pubsub_ingestor
from handlers import config
from handlers import culprit
from handlers import failure_log
from handlers import help_triage
from handlers import home
from handlers import list_analyses
from handlers import obscure_emails
from handlers import pipeline_errors_dashboard
from handlers import process_failure_analysis_requests
from handlers import process_flake_analysis_request
from handlers import swarming_pubsub_pipeline_callback
from handlers import triage_suspected_cl
from handlers import try_job_dashboard
from handlers import try_job_pubsub_pipeline_callback
from handlers.flake import check_flake
from handlers.flake import flake_culprit
from handlers.flake import list_flakes
from handlers.flake import triage_flake_analysis
from handlers.flake.detection import show_flake

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
    ('/waterfall/change-auto-revert-setting',
     change_auto_revert_setting.ChangeAutoRevertSetting),
    ('/waterfall/check-duplicate-failures',
     check_duplicate_failures.CheckDuplicateFailures),
    ('/waterfall/check-flake', check_flake.CheckFlake),
    ('/waterfall/check-trybot-mapping',
     check_trybot_mapping.CheckTrybotMapping),
    ('/waterfall/config', config.Configuration),
    ('/waterfall/culprit', culprit.Culprit),
    ('/waterfall/failure', build_failure.BuildFailure),
    ('/waterfall/failure-log', failure_log.FailureLog),
    ('/waterfall/flake', check_flake.CheckFlake),
    ('/waterfall/flake/flake-culprit', flake_culprit.FlakeCulprit),
    ('/waterfall/help-triage', help_triage.HelpTriage),
    ('/waterfall/list-failures', list_analyses.ListAnalyses),
    ('/waterfall/list-flakes', list_flakes.ListFlakes),
    ('/waterfall/list-analyses', list_analyses.ListAnalyses),
    ('/waterfall/pipeline-errors-dashboard',
     pipeline_errors_dashboard.PipelineErrorsDashboard),
    ('/waterfall/triage-flake-analysis',
     triage_flake_analysis.TriageFlakeAnalysis),
    ('/waterfall/triage-suspected-cl', triage_suspected_cl.TriageSuspectedCl),
    ('/waterfall/try-job-dashboard', try_job_dashboard.TryJobDashboard),
]
waterfall_frontend_web_application = webapp2.WSGIApplication(
    waterfall_frontend_web_pages_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(waterfall_frontend_web_application)

# flake detection frontend.
flake_detection_frontend_web_pages_handler_mappings = [
    ('/flake/detection/show-flake', show_flake.ShowFlake),
]
flake_detection_frontend_web_application = webapp2.WSGIApplication(
    flake_detection_frontend_web_pages_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(flake_detection_frontend_web_application)
