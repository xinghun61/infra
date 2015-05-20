# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import copy
import tempfile
import unittest

import mock

from monacq.proto import metrics_pb2
from testing_support import auto_stub

from infra.libs.ts_mon import errors
from infra.libs.ts_mon import interface
from infra.libs.ts_mon.test import stubs


class GlobalsTest(auto_stub.TestCase):

  def setUp(self):
    super(GlobalsTest, self).setUp()
    self.mock(interface, '_state', stubs.MockState())

  @mock.patch('socket.getfqdn')
  @mock.patch('infra.libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.targets.DeviceTarget')
  def test_default_monitor_args(self, fake_target, fake_monitor, fake_fqdn):
    singleton = object()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'slave1-a1.reg.tld'
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage')
    self.assertIs(interface._state.global_monitor, singleton)
    fake_target.assert_called_once_with('reg', '1', 'slave1-a1')
    self.assertIs(interface._state.default_target, singleton)
    self.assertEquals(args.ts_mon_flush, 'manual')

  @mock.patch('socket.getfqdn')
  @mock.patch('infra.libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.targets.DeviceTarget')
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

  @mock.patch('infra.libs.ts_mon.monitors.ApiMonitor')
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

  @mock.patch('infra.libs.ts_mon.monitors.DiskMonitor')
  def test_dryrun_args(self, fake_monitor):
    singleton = object()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-endpoint', 'file://foo.txt'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with('foo.txt')
    self.assertIs(interface._state.global_monitor, singleton)

  @mock.patch('infra.libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.targets.DeviceTarget')
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

  @mock.patch('infra.libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra.libs.ts_mon.targets.TaskTarget')
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

  @mock.patch('infra.libs.ts_mon.monitors.NullMonitor')
  def test_no_args(self, fake_monitor):
    singleton = object()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args([])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once()
    self.assertIs(interface._state.global_monitor, singleton)

  def test_send(self):
    interface._state.flush_mode = 'all'
    interface._state.global_monitor = stubs.MockMonitor()

    def serialize_to(pb, default_target=None): # pylint: disable=unused-argument
      pb.data.add().name = 'foo'

    fake_metric = mock.Mock()
    fake_metric.serialize_to = mock.Mock(side_effect=serialize_to)

    interface.send(fake_metric)
    interface._state.global_monitor.send.assert_called_once()
    proto = interface._state.global_monitor.send.call_args[0][0]
    self.assertEqual(1, len(proto.data))
    self.assertEqual('foo', proto.data[0].name)

  def test_send_manual(self):
    interface._state.flush_mode = 'manual'
    interface._state.global_monitor = stubs.MockMonitor()

    fake_metric = mock.Mock()
    fake_metric.serialize_to = mock.Mock()

    interface.send(fake_metric)
    self.assertFalse(interface._state.global_monitor.send.called)
    self.assertFalse(fake_metric.serialize_to.called)

  def test_send_all_raises(self):
    self.assertIsNone(interface._state.global_monitor)
    interface._state.flush_mode = 'all'
    with self.assertRaises(errors.MonitoringNoConfiguredMonitorError):
      interface.send(mock.MagicMock())

  def test_send_manual_works(self):
    self.assertIsNone(interface._state.global_monitor)
    interface._state.flush_mode = 'manual'
    interface.send(mock.MagicMock())

  def test_flush(self):
    interface._state.global_monitor = stubs.MockMonitor()

    def serialize_to(pb, default_target=None): # pylint: disable=unused-argument
      pb.data.add().name = 'foo'

    fake_metric = mock.Mock()
    fake_metric.serialize_to = mock.Mock(side_effect=serialize_to)
    interface._state.metrics.add(fake_metric)

    interface.flush()
    interface._state.global_monitor.send.assert_called_once()
    proto = interface._state.global_monitor.send.call_args[0][0]
    self.assertEqual(1, len(proto.data))
    self.assertEqual('foo', proto.data[0].name)

  def test_flush_raises(self):
    self.assertIsNone(interface._state.global_monitor)
    with self.assertRaises(errors.MonitoringNoConfiguredMonitorError):
      interface.flush()

  def test_register_unregister(self):
    fake_metric = mock.Mock()
    self.assertEqual(0, len(interface._state.metrics))
    interface.register(fake_metric)
    self.assertEqual(1, len(interface._state.metrics))
    interface.unregister(fake_metric)
    self.assertEqual(0, len(interface._state.metrics))

  def test_identical_register(self):
    fake_metric = mock.Mock(_name='foo')
    interface.register(fake_metric)
    interface.register(fake_metric)
    self.assertEqual(1, len(interface._state.metrics))

  def test_duplicate_register_raises(self):
    fake_metric = mock.Mock(_name='foo')
    phake_metric = mock.Mock(_name='foo')
    interface.register(fake_metric)
    with self.assertRaises(errors.MonitoringDuplicateRegistrationError):
      interface.register(phake_metric)
    self.assertEqual(1, len(interface._state.metrics))

  def test_unregister_missing_raises(self):
    fake_metric = mock.Mock(_name='foo')
    self.assertEqual(0, len(interface._state.metrics))
    with self.assertRaises(KeyError):
      interface.unregister(fake_metric)
