# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import socket
import sys
import urlparse
import re

import monitors
import interface
from common import standard_metrics
from common import targets


def initialize(endpoint=None, flush='manual', job_name=None,
               service_name=None, instance=0):
  """Initialize the global monitor.

  Also initializes the default target if endpoint argument is supplied.
  If they aren't, all created metrics will have to supply their own target.
  This is generally a bad idea, as many libraries rely on the default target
  being set up.

  Args:
    endpoint: url (in format pubsub://project/topic) to post ts_mon metrics to
    flush:  metric push behavior: all (send every metric individually),
            or manual (only send when flush() is called)
    job_name: name of the job instance of the task
    instance: number of instance for this task
    service_name: name of service being monitored

  """
  hostname = socket.getfqdn().split('.')[0]
  try:
    region = fqdn.split('.')[1]
  except:
    region = ''

  url = urlparse.urlparse(endpoint)
  project = url.netloc
  topic = url.path.strip('/')
  interface.state.global_monitor = monitors.PubSubMonitor(project, topic)

  # Reimplement ArgumentParser.error, since we don't have access to the parser
  if not service_name:
    logging.error('service_name variable is not set for task.')
  if not job_name:  # pragma: no cover
    logging.error('job_name variable is not set for task.')
  interface.state.target = targets.TaskTarget(
      service_name, job_name, region, hostname, instance)

  interface.state.flush_mode = flush

  standard_metrics.init()
