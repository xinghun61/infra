# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import gae_ts_mon

from backend.handlers import rerun_analysis
from backend.handlers import update_component_config
from gae_libs.pipeline_wrapper import pipeline_handlers


# For appengine pipeline running on backend modules.
pipeline_backend_application = pipeline_handlers._APP
gae_ts_mon.initialize(pipeline_backend_application)


backend_handler_mappings = [
    ('/process/update-component-config',
     update_component_config.UpdateComponentConfig),
    ('/process/rerun-analysis', rerun_analysis.RerunAnalysis)
]
backend_app = webapp2.WSGIApplication(backend_handler_mappings, debug=False)
gae_ts_mon.initialize(backend_app)
