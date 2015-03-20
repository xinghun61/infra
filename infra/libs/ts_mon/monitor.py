# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing the monitoring interface for tasks or devices.

Usage:
  import argparse
  from infra.libs import ts_mon

  p = argparse.ArgumentParser()
  ts_mon.add_argparse_options(p)
  args = p.parse_args()  # Must contain info for Monitor (and optionally Target)
  ts_mon.process_argparse_options(args)

  # Will use the default Target set up via command line args:
  m = ts_mon.BooleanMetric('/my/metric/name', fields={'foo': 1, 'bar': 'baz'})
  m.set(True)

  # Use a custom Target:
  t = ts_mon.TaskTarget('service', 'job', 'region', 'host')  # or DeviceTarget
  m2 = ts_mon.GaugeMetric('/my/metric/name2', fields={'asdf': 'qwer'}, target=t)
  m2.set(5)

Library usage:
  from infra.libs.ts_mon import CounterMetric
  # No need to set up Monitor or Target, assume calling code did that.
  c = CounterMetric('/my/counter', fields={'source': 'mylibrary'})
  c.set(0)
  for x in range(100):
    c.increment()
"""


import logging
import os

from monacq import acquisition_api
from monacq.proto import metrics_pb2

from infra.libs import logs


def _logging_callback(resp, content):  # pragma: no cover
  logging.debug(repr(resp))
  logging.debug(content)


class Monitor(object):
  """Abstract base class encapsulating the ability to collect and send metrics.

  This is a singleton class. There should only be one instance of a Monitor at
  a time. It will be created and initialized by process_argparse_options. It
  must exist in order for any metrics to be sent, although both Targets and
  Metrics may be initialized before the underlying Monitor. If it does not exist
  at the time that a Metric is sent, an exception will be raised.
  """
  @staticmethod
  def _wrap_proto(data):
    """Normalize MetricsData, list(MetricsData), and MetricsCollection.

    Args:
      input: A MetricsData, list of MetricsData, or a MetricsCollection.

    Returns:
      A MetricsCollection with the appropriate data attribute set.
    """
    if isinstance(data, metrics_pb2.MetricsCollection):
      ret = data
    elif isinstance(data, list):
      ret = metrics_pb2.MetricsCollection(data=data)
    else:
      ret = metrics_pb2.MetricsCollection(data=[data])
    return ret


class ApiMonitor(Monitor):
  """Class which sends metrics to the monitoring api, the default behavior."""
  def __init__(self, credsfile, endpoint):
    """Process monitoring related command line flags and initialize api.

    Args:
      credsfile (str): path to the credentials json file
      endpoint (str): url of the monitoring endpoint to hit
    """
    creds = acquisition_api.AcquisitionCredential.Load(
        os.path.abspath(credsfile))
    api = acquisition_api.AcquisitionApi(creds, endpoint)
    api.SetResponseCallback(_logging_callback)
    self._api = api

  def send(self, metric_pb):
    """Send a metric proto to the monitoring api.

    Args:
      metric_pb (MetricsData or MetricsCollection): the metric protobuf to send
    """
    self._api.Send(self._wrap_proto(metric_pb))


class DiskMonitor(Monitor):
  """Class which writes metrics to a local file for debugging."""
  def __init__(self, filepath):
    self._logger = logging.getLogger('__name__')
    filehandler = logging.FileHandler(filepath, 'a')
    logs.add_handler(self._logger, handler=filehandler, level=logging.INFO)

  def send(self, metric_pb):
    self._logger.info('\n' + str(self._wrap_proto(metric_pb)))
