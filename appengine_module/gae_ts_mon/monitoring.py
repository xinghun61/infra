#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send system monitoring data to the timeseries monitoring API."""

import logging
import webapp2

from common.metrics import *
from common.http_metrics import (
    access_count, durations, request_bytes, response_bytes, response_status)
import config
import interface

from google.appengine.api import app_identity
from google.appengine.api import modules

import os
import sys


MONACQ_ENDPOINT = 'pubsub://chrome-infra-mon-pubsub/monacq'


class InitializeMonitoringHandler(webapp2.RequestHandler):

  def get(self):
    service = app_identity.get_application_id()
    version = modules.get_current_version_name()
    instance_id = hash(modules.get_current_instance_id()) % 10
    endpoint = MONACQ_ENDPOINT
    config.initialize(job_name=version, instance=instance_id,
                      service_name=service, endpoint=endpoint)
    self.response.set_status(200, 'Initialized instance of ts_mon.')


class MonitoringHandler(webapp2.RequestHandler):

  ''' Called by cron jobs every 5 minutes to update metrics. '''
  def get(self, key=None):
    interface.flush()
    logging.info('Metrics updated.')
    return


app = webapp2.WSGIApplication([
    ('/_ah/start', InitializeMonitoringHandler),
    ('/monitoring', MonitoringHandler),
    ('/monitoring/(.*)', MonitoringHandler)
], debug=True)
