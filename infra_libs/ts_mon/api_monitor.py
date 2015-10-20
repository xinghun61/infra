# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Monitor object which sends metrics to the monitoring api."""


import logging
import os

from monacq import acquisition_api

from infra_libs import httplib2_utils
from infra_libs.ts_mon.common import monitors


def _logging_callback(resp, content):
  logging.debug(repr(resp))
  logging.debug(content)


class ApiMonitor(monitors.Monitor):
  """Class which sends metrics to the monitoring api."""
  def __init__(self, credsfile, endpoint, use_instrumented_http=True):
    """Process monitoring related command line flags and initialize api.

    Args:
      credsfile (str): path to the credentials json file
      endpoint (str): url of the monitoring endpoint to hit
    """

    if credsfile in (monitors.APPENGINE_CREDENTIALS,
                     monitors.GCE_CREDENTIALS):
      raise NotImplementedError(
          'Appengine or GCE service accounts are not supported for ApiMonitor')

    creds = acquisition_api.AcquisitionCredential.Load(
        os.path.abspath(credsfile))
    api = acquisition_api.AcquisitionApi(creds, endpoint)
    api.SetResponseCallback(_logging_callback)

    if use_instrumented_http:
      api.SetHttp(httplib2_utils.InstrumentedHttp('acq-mon-api'))

    self._api = api

  def send(self, metric_pb):
    """Send a metric proto to the monitoring api.

    Args:
      metric_pb (MetricsData or MetricsCollection): the metric protobuf to send
    """
    try:
      self._api.Send(self._wrap_proto(metric_pb))
    except acquisition_api.AcquisitionApiRequestException as e:
      logging.error('Failed to send the metrics: %s', e)

