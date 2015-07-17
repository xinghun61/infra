# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import tempfile
import unittest

import mock

from monacq.proto import metrics_pb2

from infra_libs.ts_mon import monitors
import infra_libs


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

  @mock.patch('infra_libs.ts_mon.monitors.acquisition_api')
  def test_instrumented(self, fake_api):
    m = monitors.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api')
    m.send(metrics_pb2.MetricsData(name='m1'))

    api = fake_api.AcquisitionApi.return_value
    api.SetHttp.assert_called_once()
    self.assertIsInstance(api.SetHttp.call_args[0][0],
                          infra_libs.InstrumentedHttp)

  @mock.patch('infra_libs.ts_mon.monitors.acquisition_api')
  def test_not_instrumented(self, fake_api):
    m = monitors.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api',
                            use_instrumented_http=False)
    m.send(metrics_pb2.MetricsData(name='m1'))

    self.assertFalse(fake_api.SetHttp.called)


class PubSubMonitorTest(unittest.TestCase):

  @mock.patch('infra_libs.ts_mon.monitors.httplib2')
  @mock.patch('infra_libs.ts_mon.monitors.discovery')
  @mock.patch('infra_libs.ts_mon.monitors.GoogleCredentials')
  def test_init_service_account(self, gc, discovery, httplib2):
    m_open = mock.mock_open(read_data='{"type": "service_account"}')
    creds = gc.from_stream.return_value
    scoped_creds = creds.create_scoped.return_value
    http_mock = httplib2.Http.return_value
    with mock.patch('infra_libs.ts_mon.monitors.open', m_open, create=True):
      mon = monitors.PubSubMonitor('/path/to/creds.p8.json', 'myproject',
                                   'mytopic')

    m_open.assert_called_once_with('/path/to/creds.p8.json', 'r')
    creds.create_scoped.assert_called_once_with(monitors.PubSubMonitor._SCOPES)
    scoped_creds.authorize.assert_called_once_with(http_mock)
    discovery.build.assert_called_once_with('pubsub', 'v1', http=http_mock)
    self.assertEquals(mon._topic, 'projects/myproject/topics/mytopic')

  @mock.patch('infra_libs.ts_mon.monitors.httplib2')
  @mock.patch('infra_libs.ts_mon.monitors.discovery')
  @mock.patch('infra_libs.ts_mon.monitors.Storage')
  def test_init_storage(self, storage, discovery, httplib2):
    storage_inst = mock.Mock()
    storage.return_value = storage_inst
    creds = storage_inst.get.return_value

    m_open = mock.mock_open(read_data='{}')
    http_mock = httplib2.Http.return_value
    with mock.patch('infra_libs.ts_mon.monitors.open', m_open, create=True):
      mon = monitors.PubSubMonitor('/path/to/creds.p8.json', 'myproject',
                                   'mytopic')

    m_open.assert_called_once_with('/path/to/creds.p8.json', 'r')
    storage_inst.get.assert_called_once_with()
    creds.authorize.assert_called_once_with(http_mock)
    discovery.build.assert_called_once_with('pubsub', 'v1', http=http_mock)
    self.assertEquals(mon._topic, 'projects/myproject/topics/mytopic')

  @mock.patch('infra_libs.ts_mon.monitors.PubSubMonitor._initialize')
  def test_send(self, _psmonitor):
    mon = monitors.PubSubMonitor('/path/to/creds.p8.json', 'myproject',
                                 'mytopic')
    mon._api = mock.MagicMock()
    mon._topic = 'mytopic'

    metric1 = metrics_pb2.MetricsData(name='m1')
    mon.send(metric1)
    metric2 = metrics_pb2.MetricsData(name='m2')
    mon.send([metric1, metric2])
    collection = metrics_pb2.MetricsCollection(data=[metric1, metric2])
    mon.send(collection)

    def message(pb):
      pb = monitors.Monitor._wrap_proto(pb)
      return {'messages': [{'data': base64.b64encode(pb.SerializeToString())}]}
    publish = mon._api.projects.return_value.topics.return_value.publish
    publish.assert_has_calls([
        mock.call(topic='mytopic', body=message(metric1)),
        mock.call().execute(num_retries=5),
        mock.call(topic='mytopic', body=message([metric1, metric2])),
        mock.call().execute(num_retries=5),
        mock.call(topic='mytopic', body=message(collection)),
        mock.call().execute(num_retries=5),
        ])


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
