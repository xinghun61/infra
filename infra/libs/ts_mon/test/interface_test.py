# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import copy
import tempfile
import unittest

import mock

import infra.libs.ts_mon.interface as interface

from infra.libs.ts_mon.errors import MonitoringNoConfiguredMonitorError
from infra.libs.ts_mon.errors import MonitoringNoConfiguredTargetError


class GlobalsTest(unittest.TestCase):

  def setUp(self):
    interface._state = interface.State()

  def tearDown(self):
    interface._state = interface.State()

  @mock.patch('socket.getfqdn')
  @mock.patch('infra.libs.ts_mon.interface.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.interface.DeviceTarget')
  def test_default_monitor_args(self, fake_target, fake_monitor, fake_fqdn):
    singleton = object()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'foo100.reg.tld'
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage')
    self.assertIs(interface._state.global_monitor, singleton)
    fake_target.assert_called_once_with('reg', '100', 'foo100')
    self.assertIs(interface._state.default_target, singleton)
    self.assertEquals(args.ts_mon_flush, 'all')

  @mock.patch('socket.getfqdn')
  @mock.patch('infra.libs.ts_mon.interface.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.interface.DeviceTarget')
  def test_fallback_monitor_args(self, fake_target, fake_monitor, fake_fqdn):
    singleton = object()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'foo'
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage')
    self.assertIs(interface._state.global_monitor, singleton)
    fake_target.assert_called_once_with('', '', 'foo')
    self.assertIs(interface._state.default_target, singleton)

  @mock.patch('infra.libs.ts_mon.interface.ApiMonitor')
  def test_monitor_args(self, fake_monitor):
    singleton = object()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-endpoint', 'https://foo.tld/api'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json', 'https://foo.tld/api')
    self.assertIs(interface._state.global_monitor, singleton)

  @mock.patch('infra.libs.ts_mon.interface.DiskMonitor')
  def test_dryrun_args(self, fake_monitor):
    singleton = object()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-endpoint', 'file://foo.txt'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with('foo.txt')
    self.assertIs(interface._state.global_monitor, singleton)

  @mock.patch('infra.libs.ts_mon.interface.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.interface.DeviceTarget')
  def test_device_args(self, fake_target, _fake_monitor):
    singleton = object()
    fake_target.return_value = singleton
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-target-type', 'device',
                         '--ts-mon-device-region', 'reg',
                         '--ts-mon-device-network', 'net',
                         '--ts-mon-device-hostname', 'host'])
    interface.process_argparse_options(args)
    fake_target.assert_called_once_with('reg', 'net', 'host')
    self.assertIs(interface._state.default_target, singleton)

  @mock.patch('infra.libs.ts_mon.interface.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.interface.TaskTarget')
  def test_task_args(self, fake_target, _fake_monitor):
    singleton = object()
    fake_target.return_value = singleton
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-target-type', 'task',
                         '--ts-mon-task-service-name', 'serv',
                         '--ts-mon-task-job-name', 'job',
                         '--ts-mon-task-region', 'reg',
                         '--ts-mon-task-hostname', 'host',
                         '--ts-mon-task-number', '1'])
    interface.process_argparse_options(args)
    fake_target.assert_called_once_with('serv', 'job' ,'reg', 'host', 1)
    self.assertIs(interface._state.default_target, singleton)

  @mock.patch('infra.libs.ts_mon.interface._state')
  def test_send(self, fake_state):
    fake_metric = mock.MagicMock()
    fake_proto = mock.MagicMock().serialize()
    fake_metric.serialize.return_value = fake_proto
    interface._state.flush_mode = 'all'
    interface.send(fake_metric)
    fake_state.global_monitor.send.assert_called_once_with(fake_proto)

  @mock.patch('infra.libs.ts_mon.interface._state')
  def test_send_stores(self, fake_state):
    fake_metric = mock.MagicMock()
    fake_proto = mock.MagicMock().serialize()
    fake_metric.serialize.return_value = fake_proto
    interface._state.flush_mode = 'manual'
    interface.send(fake_metric)
    fake_state.metric_store.append.assert_called_once_with(fake_proto)

  def test_send_raises(self):
    self.assertIsNone(interface._state.global_monitor)
    with self.assertRaises(MonitoringNoConfiguredMonitorError):
      interface.send(mock.MagicMock())

  @mock.patch('infra.libs.ts_mon.interface._state')
  def test_flush(self, fake_state):
    fake_state.metric_store = [2, 'foo', True]
    interface.flush()
    fake_state.global_monitor.send.assert_called_once_with([2, 'foo', True])
    self.assertEqual(fake_state.metric_store, [])
