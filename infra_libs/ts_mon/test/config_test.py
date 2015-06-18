# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import tempfile
import unittest

import mock

from testing_support import auto_stub

from infra_libs.ts_mon import config
from infra_libs.ts_mon import interface
from infra_libs.ts_mon import standard_metrics
from infra_libs.ts_mon.test import stubs


class GlobalsTest(auto_stub.TestCase):

  def setUp(self):
    super(GlobalsTest, self).setUp()
    self.mock(interface, 'state', stubs.MockState())
    self.mock(config, 'load_machine_config', lambda x: {})

  def tearDown(self):
    # It's important to call close() before un-setting the mock state object,
    # because any FlushThread started by the test is stored in that mock state
    # and needs to be stopped before running any other tests.
    interface.close()
    super(GlobalsTest, self).tearDown()

  @mock.patch('socket.getfqdn')
  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra_libs.ts_mon.targets.DeviceTarget')
  def test_default_monitor_args(self, fake_target, fake_monitor, fake_fqdn):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'slave1-a1.reg.tld'
    p = argparse.ArgumentParser()
    config.add_argparse_options(p)
    args = p.parse_args([
        '--ts-mon-credentials', '/path/to/creds.p8.json',
        '--ts-mon-endpoint',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage'])
    config.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage')
    self.assertIs(interface.state.global_monitor, singleton)
    fake_target.assert_called_once_with('reg', '1', 'slave1-a1')
    self.assertIs(interface.state.default_target, singleton)
    self.assertEquals(args.ts_mon_flush, 'auto')
    self.assertIsNotNone(interface.state.flush_thread)
    self.assertTrue(standard_metrics.up.get())

  @mock.patch('socket.getfqdn')
  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra_libs.ts_mon.targets.DeviceTarget')
  def test_fallback_monitor_args(self, fake_target, fake_monitor, fake_fqdn):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'foo'
    p = argparse.ArgumentParser()
    config.add_argparse_options(p)
    args = p.parse_args([
        '--ts-mon-credentials', '/path/to/creds.p8.json',
        '--ts-mon-endpoint',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage'])
    config.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage')
    self.assertIs(interface.state.global_monitor, singleton)
    fake_target.assert_called_once_with('', '', 'foo')
    self.assertIs(interface.state.default_target, singleton)

  @mock.patch('socket.getfqdn')
  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra_libs.ts_mon.targets.DeviceTarget')
  def test_manual_flush(self, fake_target, fake_monitor, fake_fqdn):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'foo'
    p = argparse.ArgumentParser()
    config.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-flush', 'manual'])
    config.process_argparse_options(args)
    self.assertIsNone(interface.state.flush_thread)

  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  def test_monitor_args(self, fake_monitor):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    config.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-endpoint', 'https://foo.tld/api'])
    config.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json', 'https://foo.tld/api')
    self.assertIs(interface.state.global_monitor, singleton)

  @mock.patch('infra_libs.ts_mon.monitors.DiskMonitor')
  def test_dryrun_args(self, fake_monitor):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    config.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-endpoint', 'file://foo.txt'])
    config.process_argparse_options(args)
    fake_monitor.assert_called_once_with('foo.txt')
    self.assertIs(interface.state.global_monitor, singleton)

  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra_libs.ts_mon.targets.DeviceTarget')
  def test_device_args(self, fake_target, _fake_monitor):
    singleton = mock.Mock()
    fake_target.return_value = singleton
    p = argparse.ArgumentParser()
    config.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-target-type', 'device',
                         '--ts-mon-device-region', 'reg',
                         '--ts-mon-device-network', 'net',
                         '--ts-mon-device-hostname', 'host'])
    config.process_argparse_options(args)
    fake_target.assert_called_once_with('reg', 'net', 'host')
    self.assertIs(interface.state.default_target, singleton)

  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra_libs.ts_mon.targets.TaskTarget')
  def test_task_args(self, fake_target, _fake_monitor):
    singleton = mock.Mock()
    fake_target.return_value = singleton
    p = argparse.ArgumentParser()
    config.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-target-type', 'task',
                         '--ts-mon-task-service-name', 'serv',
                         '--ts-mon-task-job-name', 'job',
                         '--ts-mon-task-region', 'reg',
                         '--ts-mon-task-hostname', 'host',
                         '--ts-mon-task-number', '1'])
    config.process_argparse_options(args)
    fake_target.assert_called_once_with('serv', 'job' ,'reg', 'host', 1)
    self.assertIs(interface.state.default_target, singleton)

  @mock.patch('infra_libs.ts_mon.monitors.NullMonitor')
  def test_no_args(self, fake_monitor):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    config.add_argparse_options(p)
    args = p.parse_args([])
    config.process_argparse_options(args)
    fake_monitor.assert_called_once()
    self.assertIs(interface.state.global_monitor, singleton)


class ConfigTest(unittest.TestCase):

  def test_load_machine_config(self):
    with tempfile.NamedTemporaryFile() as fh:
      json.dump({'foo': 'bar'}, fh)
      fh.flush()
      self.assertEquals({'foo': 'bar'}, config.load_machine_config(fh.name))

  def test_load_machine_config_bad(self):
    with tempfile.NamedTemporaryFile() as fh:
      fh.write('not a json file')
      fh.flush()
      with self.assertRaises(ValueError):
        config.load_machine_config(fh.name)

  def test_load_machine_config_not_exists(self):
    self.assertEquals({}, config.load_machine_config('does not exist'))
