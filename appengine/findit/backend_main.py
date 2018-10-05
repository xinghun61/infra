# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import gae_ts_mon

from gae_libs import appengine_util
from gae_libs.pipelines import pipeline_handlers
from handlers import build_ahead
from handlers import calculate_confidence_scores
from handlers import check_reverted_cls
from handlers import collect_tree_closures
from handlers import obscure_emails
from handlers import process_failure_analysis_requests
from handlers import process_flake_analysis_request
from handlers.flake.detection import detect_flakes
from handlers.flake.detection import update_flake_counts
from handlers.flake.reporting import generate_report

# For appengine pipeline running on backend module.
pipeline_backend_application = pipeline_handlers._APP
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(pipeline_backend_application)

# "waterfall-backend" module.
waterfall_backend_web_pages_handler_mappings = [
    ('/waterfall/cron/calculate-confidence-scores',
     calculate_confidence_scores.CalculateConfidenceScores),
    ('/waterfall/cron/check-reverted-cls', check_reverted_cls.CheckRevertedCLs),
    ('/waterfall/cron/collect-tree-closures',
     collect_tree_closures.CollectTreeClosures),
    ('/waterfall/cron/obscure-emails', obscure_emails.ObscureEmails),
    ('/waterfall/cron/periodic-build-ahead', build_ahead.BuildAhead),
    ('/waterfall/task/process-failure-analysis-requests',
     process_failure_analysis_requests.ProcessFailureAnalysisRequests),
    ('/waterfall/task/process-flake-analysis-request',
     process_flake_analysis_request.ProcessFlakeAnalysisRequest),
]
waterfall_backend_web_application = webapp2.WSGIApplication(
    waterfall_backend_web_pages_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(waterfall_backend_web_application)

# "flake-detection-backend" module.
flake_detection_backend_web_pages_handler_mappings = [
    ('/flake/detection/cron/detect-cq-false-rejection-flakes',
     detect_flakes.DetectCQFalseRejectionFlakesCronJob),
    ('/flake/detection/cron/generate-flakiness-report',
     generate_report.PrepareFlakinessReport),
    ('/flake/detection/cron/update-flake-counts',
     update_flake_counts.UpdateFlakeCountsCron),
    ('/flake/detection/task/detect-cq-false-rejection-flakes',
     detect_flakes.DetectCQFalseRejectionFlakes),
    ('/flake/detection/task/update-flake-counts',
     update_flake_counts.UpdateFlakeCountsTask)
]
flake_detection_backend_web_application = webapp2.WSGIApplication(
    flake_detection_backend_web_pages_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(flake_detection_backend_web_application)
