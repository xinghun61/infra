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
from handlers import check_duplicate_failures
from handlers import check_reverted_cls
from handlers import config
from handlers import culprit
from handlers import failure_log
from handlers import help_triage
from handlers import list_analyses
from handlers import monitor_alerts
from handlers import pipeline_errors_dashboard
from handlers import process_failure_analysis_requests
from handlers import process_flake_analysis_request
from handlers import swarming_push
from handlers import swarming_task
from handlers import triage_analysis
from handlers import triage_suspected_cl
from handlers import try_job
from handlers import try_job_dashboard
from handlers import try_job_push
from handlers import try_job_result
from handlers import verify_analysis
from handlers import version
from handlers.crash import crash_config
from handlers.crash import crash_handler
from handlers.crash import cracas_dashboard
from handlers.crash import cracas_result_feedback
from handlers.crash import fracas_dashboard
from handlers.crash import fracas_result_feedback
from handlers.flake import check_flake
from handlers.flake import list_flakes
from handlers.crash import triage_analysis
from handlers.flake import triage_flake_analysis


# Default module.
default_web_pages_handler_mappings = [
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
    ('/build-failure', build_failure.BuildFailure),
    ('/list-analyses', list_analyses.ListAnalyses),
    ('/pubsub/swarmingpush', swarming_push.SwarmingPush),
    ('/pubsub/tryjobpush', try_job_push.TryJobPush),
    ('/waterfall/auto-revert-metrics',
     auto_revert_metrics.AutoRevertMetrics),
    ('/waterfall/build-failure', build_failure.BuildFailure),
    ('/waterfall/calculate-confidence-scores',
     calculate_confidence_scores.CalculateConfidenceScores),
    ('/waterfall/check-duplicate-failures',
     check_duplicate_failures.CheckDuplicateFailures),
    ('/waterfall/check-flake', check_flake.CheckFlake),
    ('/waterfall/check-reverted-cls', check_reverted_cls.CheckRevertedCLs),
    ('/waterfall/config', config.Configuration),
    ('/waterfall/culprit', culprit.Culprit),
    ('/waterfall/failure', build_failure.BuildFailure),
    ('/waterfall/failure-log', failure_log.FailureLog),
    ('/waterfall/flake', check_flake.CheckFlake),
    ('/waterfall/list-flakes', list_flakes.ListFlakes),
    ('/waterfall/help-triage', help_triage.HelpTriage),
    ('/waterfall/list-analyses', list_analyses.ListAnalyses),
    ('/waterfall/monitor-alerts', monitor_alerts.MonitorAlerts),
    ('/waterfall/pipeline-errors-dashboard',
     pipeline_errors_dashboard.PipelineErrorsDashboard),
    ('/waterfall/swarming-task', swarming_task.SwarmingTask),
    ('/waterfall/triage-analysis', triage_analysis.TriageAnalysis),
    ('/waterfall/triage-flake-analysis',
     triage_flake_analysis.TriageFlakeAnalysis),
    ('/waterfall/triage-suspected-cl', triage_suspected_cl.TriageSuspectedCl),
    ('/waterfall/try-job', try_job.TryJob),
    ('/waterfall/try-job-dashboard', try_job_dashboard.TryJobDashboard),
    ('/waterfall/try-job-result', try_job_result.TryJobResult),
    ('/waterfall/verify-analysis', verify_analysis.VerifyAnalysis),
]
waterfall_frontend_web_application = webapp2.WSGIApplication(
    waterfall_frontend_web_pages_handler_mappings, debug=False)
gae_ts_mon.initialize(waterfall_frontend_web_application)


# "waterfall-backend" module.
waterfall_backend_web_pages_handler_mappings = [
    ('/waterfall/process-failure-analysis-requests',
     process_failure_analysis_requests.ProcessFailureAnalysisRequests),
    ('/waterfall/process-flake-analysis-request',
     process_flake_analysis_request.ProcessFlakeAnalysisRequest),
]
waterfall_backend_web_application = webapp2.WSGIApplication(
    waterfall_backend_web_pages_handler_mappings, debug=False)
gae_ts_mon.initialize(waterfall_backend_web_application)


# "crash-frontend" module.
crash_frontend_web_pages_handler_mappings = [
    ('/crash/config', crash_config.CrashConfig),
    ('/crash/cracas-dashboard', cracas_dashboard.CracasDashBoard),
    ('/crash/cracas-result-feedback',
     cracas_result_feedback.CracasResultFeedback),
    ('/crash/fracas-dashboard', fracas_dashboard.FracasDashBoard),
    ('/crash/fracas-result-feedback',
     fracas_result_feedback.FracasResultFeedback),
    ('/crash/triage-analysis',
     triage_analysis.TriageAnalysis),
    ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
    ('/_ah/push-handlers/crash/cracas', crash_handler.CrashHandler),
    ('/_ah/push-handlers/crash/clusterfuzz', crash_handler.CrashHandler),
]
crash_frontend_web_application = webapp2.WSGIApplication(
    crash_frontend_web_pages_handler_mappings, debug=False)
