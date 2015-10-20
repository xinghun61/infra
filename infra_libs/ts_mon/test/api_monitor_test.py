# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from monacq import acquisition_api

from infra_libs.ts_mon import api_monitor
from infra_libs.ts_mon.protos import metrics_pb2
import infra_libs


class ApiMonitorTest(unittest.TestCase):

  def test_logging_callback(self):
    """Smoke test for coverage: should not crash."""
    api_monitor._logging_callback(200, "OK")

  @mock.patch('infra_libs.ts_mon.api_monitor.acquisition_api', auto_spec=True)
  def test_init(self, fake_api):
    _ = api_monitor.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api')
    fake_api.AcquisitionCredential.Load.assert_called_once_with(
        '/path/to/creds.p8.json')
    fake_api.AcquisitionApi.assert_called_once_with(
        fake_api.AcquisitionCredential.Load.return_value,
        'https://www.tld/api')

  def test_init_gce_credential(self):
    with self.assertRaises(NotImplementedError):
      api_monitor.ApiMonitor(':gce', 'https://www.tld/api')

  @mock.patch('infra_libs.ts_mon.api_monitor.acquisition_api', auto_spec=True)
  def test_send(self, _fake_api):
    m = api_monitor.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api')
    metric1 = metrics_pb2.MetricsData(name='m1')
    m.send(metric1)
    metric2 = metrics_pb2.MetricsData(name='m2')
    m.send([metric1, metric2])
    collection = metrics_pb2.MetricsCollection(data=[metric1, metric2])
    m.send(collection)
    self.assertEquals(m._api.Send.call_count, 3)

  @mock.patch('infra_libs.ts_mon.api_monitor.acquisition_api', auto_spec=True)
  def test_instrumented(self, fake_api):
    m = api_monitor.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api')
    m.send(metrics_pb2.MetricsData(name='m1'))

    api = fake_api.AcquisitionApi.return_value
    api.SetHttp.assert_called_once()
    self.assertIsInstance(api.SetHttp.call_args[0][0],
                          infra_libs.httplib2_utils.InstrumentedHttp)

  @mock.patch('infra_libs.ts_mon.api_monitor.acquisition_api', auto_spec=True)
  def test_not_instrumented(self, fake_api):
    m = api_monitor.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api',
                            use_instrumented_http=False)
    m.send(metrics_pb2.MetricsData(name='m1'))

    self.assertFalse(fake_api.SetHttp.called)

  @mock.patch('infra_libs.ts_mon.api_monitor.acquisition_api.'
              'AcquisitionCredential', auto_spec=True)
  @mock.patch('infra_libs.ts_mon.api_monitor.acquisition_api.AcquisitionApi',
              auto_spec=True)
  def test_failed_request_should_not_crash(self, _fake_api, _fake_creds):
    m = api_monitor.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api')
    m._api.Send.side_effect = acquisition_api.AcquisitionApiRequestException()
    m.send(metrics_pb2.MetricsData(name='m1'))

