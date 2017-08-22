# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import endpoints
import webapp2

import gae_ts_mon

from findit_api import FindItApi
from gae_libs.pipeline_wrapper import pipeline_handlers
from gae_libs.pipeline_wrapper import pipeline_status_ui
from handlers import auto_revert_metrics
from handlers import build_failure
from handlers import calculate_confidence_scores
from handlers import change_auto_revert_setting
from handlers import check_duplicate_failures
from handlers import check_reverted_cls
from handlers import check_trybot_mapping
from handlers import collect_tree_closures
from handlers import config
from handlers import culprit
from handlers import failure_log
from handlers import help_triage
from handlers import home
from handlers import list_analyses
from handlers import obscure_emails
from handlers import periodic_bot_update
from handlers import pipeline_errors_dashboard
from handlers import process_failure_analysis_requests
from handlers import process_flake_analysis_request
from handlers import process_flake_swarming_task_request
from handlers import rerun_for_compare
from handlers import step_by_step_comparison
from handlers import swarmbucket_performance
from handlers import swarming_push
from handlers import triage_suspected_cl
from handlers import try_job_dashboard
from handlers import try_job_push
from handlers import version
from handlers.flake import analyze_regression_range
from handlers.flake import check_flake
from handlers.flake import flake_culprit
from handlers.flake import list_flakes
from handlers.flake import triage_flake_analysis

# Default module.
default_web_pages_handler_mappings = [
    ('/', home.Home),
    ('/version', version.Version),
]
default_web_application = webapp2.WSGIApplication(
    default_web_pages_handler_mappings, debug=False)
gae_ts_mon.initialize(default_web_application)

# Cloud Endpoint apis in the default module.
api_application = endpoints.api_server([FindItApi])

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

# For appengine pipeline running on backend modules.
pipeline_backend_application = pipeline_handlers._APP
gae_ts_mon.initialize(pipeline_backend_application)

# "waterfall-frontend" module.
waterfall_frontend_web_pages_handler_mappings = [
    ('/', home.Home),
    ('/build-failure', build_failure.BuildFailure),
    ('/list-analyses', list_analyses.ListAnalyses),
    ('/pubsub/swarmingpush', swarming_push.SwarmingPush),
    ('/pubsub/tryjobpush', try_job_push.TryJobPush),
    ('/waterfall/auto-revert-metrics', auto_revert_metrics.AutoRevertMetrics),
    ('/waterfall/build-failure', build_failure.BuildFailure),
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
    ('/waterfall/flake/analyze_regression_range',
     analyze_regression_range.AnalyzeRegressionRange),
    ('/waterfall/flake/flake-culprit', flake_culprit.FlakeCulprit),
    ('/waterfall/help-triage', help_triage.HelpTriage),
    ('/waterfall/list-failures', list_analyses.ListAnalyses),
    ('/waterfall/list-flakes', list_flakes.ListFlakes),
    ('/waterfall/list-analyses', list_analyses.ListAnalyses),
    ('/waterfall/pipeline-errors-dashboard',
     pipeline_errors_dashboard.PipelineErrorsDashboard),
    ('/waterfall/rerun-for-compare', rerun_for_compare.RerunForCompare),
    ('/waterfall/step-by-step', step_by_step_comparison.StepByStepComparison),
    ('/waterfall/swarmbucket-performance',
     swarmbucket_performance.SwarmbucketPerformance),
    ('/waterfall/triage-flake-analysis',
     triage_flake_analysis.TriageFlakeAnalysis),
    ('/waterfall/triage-suspected-cl', triage_suspected_cl.TriageSuspectedCl),
    ('/waterfall/try-job-dashboard', try_job_dashboard.TryJobDashboard),
]
waterfall_frontend_web_application = webapp2.WSGIApplication(
    waterfall_frontend_web_pages_handler_mappings, debug=False)
gae_ts_mon.initialize(waterfall_frontend_web_application)

# "waterfall-backend" module.
waterfall_backend_web_pages_handler_mappings = [
    ('/waterfall/cron/calculate-confidence-scores',
     calculate_confidence_scores.CalculateConfidenceScores),
    ('/waterfall/cron/check-reverted-cls',
     check_reverted_cls.CheckRevertedCLs),
    ('/waterfall/cron/collect-tree-closures',
     collect_tree_closures.CollectTreeClosures),
    ('/waterfall/cron/obscure-emails', obscure_emails.ObscureEmails),
    ('/waterfall/cron/periodic-bot-update',
     periodic_bot_update.PeriodicBotUpdate),
    ('/waterfall/task/process-failure-analysis-requests',
     process_failure_analysis_requests.ProcessFailureAnalysisRequests),
    ('/waterfall/task/process-flake-analysis-request',
     process_flake_analysis_request.ProcessFlakeAnalysisRequest),
    ('/waterfall/task/process-flake-swarming-task-request',
     process_flake_swarming_task_request.ProcessFlakeSwarmingTaskRequest),
]
waterfall_backend_web_application = webapp2.WSGIApplication(
    waterfall_backend_web_pages_handler_mappings, debug=False)
gae_ts_mon.initialize(waterfall_backend_web_application)
