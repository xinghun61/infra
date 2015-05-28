# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import tempfile
import unittest

import mock

from monacq.proto import metrics_pb2

from infra_libs.ts_mon import monitors


class MonitorTest(unittest.TestCase):

  def test_send(self):
    m = monitors.Monitor()
    metric1 = metrics_pb2.MetricsData(name='m1')
    with self.assertRaises(NotImplementedError):
      m.send(metric1)


class ApiMonitorTest(unittest.TestCase):

  @mock.patch('infra_libs.ts_mon.monitors.acquisition_api')
  def test_init(self, fake_api):
    _ = monitors.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api')
    fake_api.AcquisitionCredential.Load.assert_called_once_with(
        '/path/to/creds.p8.json')
    fake_api.AcquisitionApi.assert_called_once_with(
        fake_api.AcquisitionCredential.Load.return_value,
        'https://www.tld/api')

  @mock.patch('infra_libs.ts_mon.monitors.acquisition_api')
  def test_send(self, _fake_api):
    m = monitors.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api')
    metric1 = metrics_pb2.MetricsData(name='m1')
    m.send(metric1)
    metric2 = metrics_pb2.MetricsData(name='m2')
    m.send([metric1, metric2])
    collection = metrics_pb2.MetricsCollection(data=[metric1, metric2])
    m.send(collection)
    self.assertEquals(m._api.Send.call_count, 3)


class DiskMonitorTest(unittest.TestCase):

  def test_send(self):
    with tempfile.NamedTemporaryFile(delete=True) as f:
      m = monitors.DiskMonitor(f.name)
      metric1 = metrics_pb2.MetricsData(name='m1')
      m.send(metric1)
      metric2 = metrics_pb2.MetricsData(name='m2')
      m.send([metric1, metric2])
      collection = metrics_pb2.MetricsCollection(data=[metric1, metric2])
      m.send(collection)
      output = f.read()
    self.assertEquals(output.count('data {\n  name: "m1"\n}'), 3)
    self.assertEquals(output.count('data {\n  name: "m2"\n}'), 2)


class NullMonitorTest(unittest.TestCase):

  def test_send(self):
    m = monitors.NullMonitor()
    metric1 = metrics_pb2.MetricsData(name='m1')
    m.send(metric1)
