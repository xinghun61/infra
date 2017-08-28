# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import webapp2

from dataflow_pipeline.trigger_pipeline_handler import TriggerPipelineHandler
from dataflow_pipeline.convert_data_pipeline_handler import (
    ConvertDataPipelineHandler)
from common.cleanup_gcs import CleanupGCSHandler
from handlers.rerun_request_handler import RerunRequestHandler


app = webapp2.WSGIApplication([
    ('/cron/trigger-pipeline', TriggerPipelineHandler),
    ('/internal/cleanup-gcs-handler', CleanupGCSHandler),
    ('/internal/convert-data-pipeline-handler', ConvertDataPipelineHandler),
    ('/internal/rerun-request-handler', RerunRequestHandler),
], debug=True)
