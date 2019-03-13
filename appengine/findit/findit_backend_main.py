# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import gae_ts_mon

from gae_libs import appengine_util
from findit_v2.handlers import build_completion_processor

# "findit-backend" module.
findit_backend_handler_mappings = [
    ('/findit/internal/v2/task/build-completed',
     build_completion_processor.BuildCompletionProcessor),
]
findit_backend_web_application = webapp2.WSGIApplication(
    findit_backend_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(findit_backend_web_application)
