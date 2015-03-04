# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import copy
import tempfile
import unittest

import mock

import infra.libs.ts_mon.monitor as monitor

from infra.libs.ts_mon.errors import MonitoringNoConfiguredMonitorError
from infra.libs.ts_mon.errors import MonitoringNoConfiguredTargetError


class GlobalsTest(unittest.TestCase):

  def setUp(self):
    monitor._global_monitor = None
    monitor._default_target = None

  def tearDown(self):
    monitor._global_monitor = None
    monitor._default_target = None

  @mock.patch('socket.getfqdn')
  @mock.patch('infra.libs.ts_mon.monitor.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.monitor.DeviceTarget')
  def test_default_monitor_args(self, fake_target, fake_monitor, fake_fqdn):
    singleton = object()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'foo100.reg.tld'
    p = argparse.ArgumentParser()
    monitor.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json'])
    monitor.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage')
    self.assertIs(monitor._global_monitor, singleton)
    fake_target.assert_called_once_with('reg', '100', 'foo100')
    self.assertIs(monitor._default_target, singleton)

  @mock.patch('socket.getfqdn')
  @mock.patch('infra.libs.ts_mon.monitor.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.monitor.DeviceTarget')
  def test_fallback_monitor_args(self, fake_target, fake_monitor, fake_fqdn):
    singleton = object()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'foo'
    p = argparse.ArgumentParser()
    monitor.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json'])
    monitor.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage')
    self.assertIs(monitor._global_monitor, singleton)
    fake_target.assert_called_once_with('', '', 'foo')
    self.assertIs(monitor._default_target, singleton)

  @mock.patch('infra.libs.ts_mon.monitor.ApiMonitor')
  def test_monitor_args(self, fake_monitor):
    singleton = object()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    monitor.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-endpoint', 'https://foo.tld/api'])
    monitor.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json', 'https://foo.tld/api')
    self.assertIs(monitor._global_monitor, singleton)

  @mock.patch('infra.libs.ts_mon.monitor.DryMonitor')
  def test_dryrun_args(self, fake_monitor):
    singleton = object()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    monitor.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-endpoint', 'file://foo.txt'])
    monitor.process_argparse_options(args)
    fake_monitor.assert_called_once_with('foo.txt')
    self.assertIs(monitor._global_monitor, singleton)

  @mock.patch('infra.libs.ts_mon.monitor.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.monitor.DeviceTarget')
  def test_device_args(self, fake_target, _fake_monitor):
    singleton = object()
    fake_target.return_value = singleton
    p = argparse.ArgumentParser()
    monitor.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-target-type', 'device',
                         '--ts-mon-device-region', 'reg',
                         '--ts-mon-device-network', 'net',
                         '--ts-mon-device-hostname', 'host'])
    monitor.process_argparse_options(args)
    fake_target.assert_called_once_with('reg', 'net', 'host')
    self.assertIs(monitor._default_target, singleton)

  @mock.patch('infra.libs.ts_mon.monitor.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.monitor.TaskTarget')
  def test_task_args(self, fake_target, _fake_monitor):
    singleton = object()
    fake_target.return_value = singleton
    p = argparse.ArgumentParser()
    monitor.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-target-type', 'task',
                         '--ts-mon-task-service-name', 'serv',
                         '--ts-mon-task-job-name', 'job',
                         '--ts-mon-task-region', 'reg',
                         '--ts-mon-task-hostname', 'host',
                         '--ts-mon-task-number', '1'])
    monitor.process_argparse_options(args)
    fake_target.assert_called_once_with('serv', 'job' ,'reg', 'host', 1)
    self.assertIs(monitor._default_target, singleton)

  @mock.patch('infra.libs.ts_mon.monitor._global_monitor')
  def test_send(self, fake_monitor):
    fake_metric = mock.MagicMock()
    monitor.send(fake_metric)
    fake_monitor.send.assert_called_once_with(fake_metric)

  def test_send_raises(self):
    self.assertIsNone(monitor._global_monitor)
    with self.assertRaises(MonitoringNoConfiguredMonitorError):
      monitor.send(mock.MagicMock())


class ApiMonitorTest(unittest.TestCase):

  @mock.patch('infra.libs.ts_mon.monitor.acquisition_api')
  def test_init(self, fake_api):
    _ = monitor.ApiMonitor('/path/to/creds.p8.json', 'https://www.tld/api')
    fake_api.AcquisitionCredential.Load.assert_called_once_with(
        '/path/to/creds.p8.json')
    fake_api.AcquisitionApi.assert_called_once_with(
        fake_api.AcquisitionCredential.Load.return_value,
        'https://www.tld/api')

  @mock.patch('infra.libs.ts_mon.monitor.acquisition_api')
  def test_send(self, _fake_api):
    fake_metric = mock.MagicMock(_name='test')
    fake_metric._target = mock.MagicMock()
    m = monitor.ApiMonitor('/path/to/creds.p8.json', 'https://www.tl/api')
    m.send(fake_metric)
    self.assertEquals(fake_metric._populate_metric_pb.call_count, 1)
    self.assertEquals(fake_metric._populate_fields_pb.call_count, 1)
    self.assertEquals(fake_metric._target._populate_target_pb.call_count, 1)
    self.assertEquals(m._api.Send.call_count, 1)

  @mock.patch('infra.libs.ts_mon.monitor.acquisition_api')
  def test_send_default(self, _fake_api):
    fake_metric = mock.MagicMock(_name='test')
    fake_metric._target = None
    monitor._default_target = mock.MagicMock()
    m = monitor.ApiMonitor('/path/to/creds.p8.json', 'https://www.tl/api')
    m.send(fake_metric)
    self.assertEquals(fake_metric._populate_metric_pb.call_count, 1)
    self.assertEquals(fake_metric._populate_fields_pb.call_count, 1)
    self.assertEquals(monitor._default_target._populate_target_pb.call_count, 1)
    self.assertEquals(m._api.Send.call_count, 1)

  @mock.patch('infra.libs.ts_mon.monitor.acquisition_api')
  def test_send_raises(self, _fake_api):
    fake_metric = mock.MagicMock(_name='test')
    fake_metric._target = None
    monitor._default_target = None
    m = monitor.ApiMonitor('/path/to/creds.p8.json', 'https://www.tl/api')
    with self.assertRaises(MonitoringNoConfiguredTargetError):
      m.send(fake_metric)


class DryMonitorTest(unittest.TestCase):

  def test_send(self):
    with tempfile.NamedTemporaryFile(delete=True) as f:
      m = monitor.DryMonitor(f.name)
      fake_metric = mock.MagicMock(_name='test')
      fake_metric._target = mock.MagicMock()
      m.send(fake_metric)
      self.assertTrue(
          any(['name: "crit/test"\n' == line for line in f.readlines()]))
