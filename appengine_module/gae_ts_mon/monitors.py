# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing the monitoring interface for tasks or devices.

In appengine, a PubSubMonitor will be automatically initialized when initialize()
is called, and there is no need to initialize it directly from this class.
"""


import base64
import json
import os

from monacq.proto import metrics_pb2

from third_party import httplib2
from third_party.apiclient import discovery
from third_party.oauth2client.client import GoogleCredentials


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

  def send(self, metric_pb):
    raise NotImplementedError()


class PubSubMonitor(Monitor):
  """Class which publishes metrics to a Cloud Pub/Sub topic."""

  _SCOPES = [
      'https://www.googleapis.com/auth/pubsub',
  ]

  def _initialize(self, project, topic):
    creds = GoogleCredentials.get_application_default()
    creds = creds.create_scoped(self._SCOPES)
    self._http = httplib2.Http()
    creds.authorize(self._http)
    self._api = discovery.build('pubsub', 'v1', http=self._http)
    self._topic = 'projects/%s/topics/%s' % (project, topic)

  def __init__(self, project, topic):
    """Process monitoring related command line flags and initialize api.

    Args:
      project (str): the name of the Pub/Sub project to publish to.
      topic (str): the name of the Pub/Sub topic to publish to.
    """
    self._initialize(project, topic)

  def send(self, metric_pb):
    """Send a metric proto to the monitoring api.

    Args:
      metric_pb (MetricsData or MetricsCollection): the metric protobuf to send
    """
    proto = self._wrap_proto(metric_pb)
    body = {
        'messages': [
          {'data': base64.b64encode(proto.SerializeToString())},
        ],
    }
    self._api.projects().topics().publish(
        topic=self._topic,
        body=body).execute(num_retries=5)


class NullMonitor(Monitor):
  """Class that doesn't send metrics anywhere."""
  def send(self, metric_pb):
    pass
