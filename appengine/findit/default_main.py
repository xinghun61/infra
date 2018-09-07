# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import gae_ts_mon

from endpoint_api import FindItApi
from gae_libs import appengine_util
from gae_libs.pipelines import pipeline_handlers
from gae_libs.pipelines import pipeline_status_ui
from handlers import completed_build_pubsub_ingestor
from handlers import home
from handlers import swarming_pubsub_pipeline_callback
from handlers import try_job_pubsub_pipeline_callback

from components import endpoints_webapp2

# Default module.
default_web_pages_handler_mappings = [
    ('/_ah/push-handlers/index-isolated-builds',
     completed_build_pubsub_ingestor.CompletedBuildPubsubIngestor),
    ('/_ah/push-handlers/swarming',
     swarming_pubsub_pipeline_callback.SwarmingPubSubPipelineCallback),
    ('/_ah/push-handlers/tryjob',
     try_job_pubsub_pipeline_callback.TryJobPubSubPipelineCallback),
    ('/', home.Home),
]
default_web_application = webapp2.WSGIApplication(
    default_web_pages_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(default_web_application)

# Cloud Endpoint apis in the default module.
api_application = endpoints_webapp2.api_server([FindItApi])
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(api_application)

# App Engine pipeline status pages in the default module.
# TODO(stgao): Move this to frontend module.
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
