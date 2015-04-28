# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import copy
import tempfile
import unittest

import mock

from monacq.proto import metrics_pb2

import infra.libs.ts_mon.interface as interface

from infra.libs.ts_mon.errors import MonitoringNoConfiguredMonitorError
from infra.libs.ts_mon.errors import MonitoringNoConfiguredTargetError


class FakeState(interface.State):
  def __init__(self):
    super(FakeState, self).__init__()
    self.global_monitor = mock.Mock()


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

  @mock.patch('infra.libs.ts_mon.interface._state', new_callable=FakeState)
  def test_send(self, fake_state):
    def serialize_to(pb, default_target=None): # pylint: disable=unused-argument
      pb.data.add().name = 'foo'

    interface._state.flush_mode = 'all'

    fake_metric = mock.Mock()
    fake_metric.serialize_to = mock.Mock(side_effect=serialize_to)

    interface.send(fake_metric)
    fake_state.global_monitor.send.assert_called_once()
    proto = fake_state.global_monitor.send.call_args[0][0]
    self.assertEqual(1, len(proto.data))
    self.assertEqual('foo', proto.data[0].name)

  @mock.patch('infra.libs.ts_mon.interface._state', new_callable=FakeState)
  def test_send_manual(self, fake_state):
    interface._state.flush_mode = 'manual'

    fake_metric = mock.Mock()
    fake_metric.serialize_to = mock.Mock()

    interface.send(fake_metric)
    self.assertFalse(fake_state.global_monitor.send.called)
    self.assertFalse(fake_metric.serialize_to.called)

  def test_send_raises(self):
    self.assertIsNone(interface._state.global_monitor)
    with self.assertRaises(MonitoringNoConfiguredMonitorError):
      interface.send(mock.MagicMock())

  @mock.patch('infra.libs.ts_mon.interface._state', new_callable=FakeState)
  def test_flush(self, fake_state):
    def serialize_to(pb, default_target=None): # pylint: disable=unused-argument
      pb.data.add().name = 'foo'

    fake_metric = mock.Mock()
    fake_metric.serialize_to = mock.Mock(side_effect=serialize_to)
    fake_state.metrics.add(fake_metric)

    interface.flush()
    fake_state.global_monitor.send.assert_called_once()
    proto = fake_state.global_monitor.send.call_args[0][0]
    self.assertEqual(1, len(proto.data))
    self.assertEqual('foo', proto.data[0].name)

  def test_flush_raises(self):
    self.assertIsNone(interface._state.global_monitor)
    with self.assertRaises(MonitoringNoConfiguredMonitorError):
      interface.flush()

  @mock.patch('infra.libs.ts_mon.interface._state', new_callable=FakeState)
  def test_register_unregister(self, fake_state):
    fake_metric = mock.Mock()
    other_fake_metric = mock.Mock()

    self.assertEqual(0, len(fake_state.metrics))
    interface.register(fake_metric)
    self.assertEqual(1, len(fake_state.metrics))

    # Registering the same one twice doesn't do anything
    interface.register(fake_metric)
    self.assertEqual(1, len(fake_state.metrics))

    # Trying to unregister something that isn't registered raises an exception.
    with self.assertRaises(KeyError):
      interface.unregister(other_fake_metric)

    self.assertEqual(1, len(fake_state.metrics))
    interface.unregister(fake_metric)
    self.assertEqual(0, len(fake_state.metrics))
