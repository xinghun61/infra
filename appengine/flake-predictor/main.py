# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import webapp2

from dataflow_pipeline.trigger_pipeline_handler import TriggerPipelineHandler


app = webapp2.WSGIApplication([
    ('/cron/trigger-pipeline', TriggerPipelineHandler)
], debug=True)
