# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import functools
import json
import tempfile
import threading
import time
import unittest

import mock

from monacq.proto import metrics_pb2
from testing_support import auto_stub

from infra_libs.ts_mon import errors
from infra_libs.ts_mon import interface
from infra_libs.ts_mon.test import stubs


class GlobalsTest(auto_stub.TestCase):

  def setUp(self):
    super(GlobalsTest, self).setUp()
    self.mock(interface, '_state', stubs.MockState())
    self.mock(interface, 'load_machine_config', lambda x: {})

  def tearDown(self):
    # It's important to call close() before un-setting the mock _state object,
    # because any FlushThread started by the test is stored in that mock _state
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
    interface.add_argparse_options(p)
    args = p.parse_args([
        '--ts-mon-credentials', '/path/to/creds.p8.json',
        '--ts-mon-endpoint',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage')
    self.assertIs(interface._state.global_monitor, singleton)
    fake_target.assert_called_once_with('reg', '1', 'slave1-a1')
    self.assertIs(interface._state.default_target, singleton)
    self.assertEquals(args.ts_mon_flush, 'auto')
    self.assertIsNotNone(interface._state.flush_thread)

  @mock.patch('socket.getfqdn')
  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra_libs.ts_mon.targets.DeviceTarget')
  def test_fallback_monitor_args(self, fake_target, fake_monitor, fake_fqdn):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'foo'
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args([
        '--ts-mon-credentials', '/path/to/creds.p8.json',
        '--ts-mon-endpoint',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json',
        'https://www.googleapis.com/acquisitions/v1_mon_shared/storage')
    self.assertIs(interface._state.global_monitor, singleton)
    fake_target.assert_called_once_with('', '', 'foo')
    self.assertIs(interface._state.default_target, singleton)

  @mock.patch('socket.getfqdn')
  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra_libs.ts_mon.targets.DeviceTarget')
  def test_manual_flush(self, fake_target, fake_monitor, fake_fqdn):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    fake_target.return_value = singleton
    fake_fqdn.return_value = 'foo'
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-flush', 'manual'])
    interface.process_argparse_options(args)
    self.assertIsNone(interface._state.flush_thread)

  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  def test_monitor_args(self, fake_monitor):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-credentials', '/path/to/creds.p8.json',
                         '--ts-mon-endpoint', 'https://foo.tld/api'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with(
        '/path/to/creds.p8.json', 'https://foo.tld/api')
    self.assertIs(interface._state.global_monitor, singleton)

  @mock.patch('infra_libs.ts_mon.monitors.DiskMonitor')
  def test_dryrun_args(self, fake_monitor):
    singleton = mock.Mock()
    fake_monitor.return_value = singleton
    p = argparse.ArgumentParser()
    interface.add_argparse_options(p)
    args = p.parse_args(['--ts-mon-endpoint', 'file://foo.txt'])
    interface.process_argparse_options(args)
    fake_monitor.assert_called_once_with('foo.txt')
    self.assertIs(interface._state.global_monitor, singleton)

  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra_libs.ts_mon.targets.DeviceTarget')
  def test_device_args(self, fake_target, _fake_monitor):
    singleton = mock.Mock()
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

  @mock.patch('infra_libs.ts_mon.monitors.ApiMonitor')
  @mock.patch('infra_libs.ts_mon.targets.TaskTarget')
  def test_task_args(self, fake_target, _fake_monitor):
    singleton = mock.Mock()
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

  @mock.patch('infra_libs.ts_mon.monitors.NullMonitor')
  def test_no_args(self, fake_monitor):
    singleton = mock.Mock()
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

  def test_close_stops_flush_thread(self):  # pragma: no cover
    interface._state.flush_thread = interface._FlushThread(10)
    interface._state.flush_thread.start()

    self.assertTrue(interface._state.flush_thread.is_alive())
    interface.close()
    self.assertFalse(interface._state.flush_thread.is_alive())


class ConfigTest(unittest.TestCase):

  def test_load_machine_config(self):
    with tempfile.NamedTemporaryFile() as fh:
      json.dump({'foo': 'bar'}, fh)
      fh.flush()
      self.assertEquals({'foo': 'bar'}, interface.load_machine_config(fh.name))

  def test_load_machine_config_bad(self):
    with tempfile.NamedTemporaryFile() as fh:
      fh.write('not a json file')
      fh.flush()
      with self.assertRaises(ValueError):
        interface.load_machine_config(fh.name)

  def test_load_machine_config_not_exists(self):
    self.assertEquals({}, interface.load_machine_config('does not exist'))


class FakeThreadingEvent(object):  # pragma: no cover
  """A fake threading.Event that doesn't use the clock for timeouts."""

  def __init__(self):
    # If not None, called inside wait() with the timeout (in seconds) to
    # increment a fake clock.
    self.increment_time_func = None

    self._is_set = False  # Return value of the next call to wait.
    self._last_wait_timeout = None  # timeout argument of the last call to wait.

    self._wait_enter_semaphore = threading.Semaphore(0)
    self._wait_exit_semaphore = threading.Semaphore(0)

  def timeout_wait(self):
    """Blocks until the next time the code under test calls wait().

    Makes the wait() call return False (indicating a timeout), and this call
    returns the timeout argument given to the wait() method.

    Called by the test.
    """

    self._wait_enter_semaphore.release()
    self._wait_exit_semaphore.acquire()
    return self._last_wait_timeout

  def set(self, blocking=True):
    """Makes the next wait() call return True.

    By default this blocks until the next call to wait(), but you can pass
    blocking=False to just set the flag, wake up any wait() in progress (if any)
    and return immediately.
    """

    self._is_set = True
    self._wait_enter_semaphore.release()
    if blocking:
      self._wait_exit_semaphore.acquire()

  def wait(self, timeout):
    """Block until either set() or timeout_wait() is called by the test."""

    self._wait_enter_semaphore.acquire()
    self._last_wait_timeout = timeout
    if self.increment_time_func is not None:  # pragma: no cover
      self.increment_time_func(timeout)
    ret = self._is_set
    self._wait_exit_semaphore.release()
    return ret


# TODO(pgervais,500046): re-enable these tests when the issue is understood.
class FlushThreadTest(unittest.TestCase):  # pragma: no cover

  def setUp(self):
    mock.patch('infra_libs.ts_mon.interface.flush').start()
    mock.patch('time.time').start()

    self.fake_time = 0
    time.time.side_effect = lambda: self.fake_time

    self.stop_event = FakeThreadingEvent()
    self.stop_event.increment_time_func = self.increment_time

    self.t = interface._FlushThread(60, stop_event=self.stop_event)

  def increment_time(self, delta):
    self.fake_time += delta

  def tearDown(self):
    # Ensure the thread exits.
    self.stop_event.set(blocking=False)
    self.t.join()

    mock.patch.stopall()

  def test_run_calls_flush(self):
    self.t.start()

    self.assertEqual(0, interface.flush.call_count)

    # The wait is for the whole interval.
    self.assertEqual(60, self.stop_event.timeout_wait())

    # Return from the second wait, which exits the thread.
    self.stop_event.set()
    self.t.join()
    self.assertEqual(2, interface.flush.call_count)

  def test_run_catches_exceptions(self):
    interface.flush.side_effect = Exception()
    self.t.start()

    self.stop_event.timeout_wait()
    # flush is called now and raises an exception.  The exception is caught, so
    # wait is called again.

    # Do it again to make sure the exception doesn't terminate the loop.
    self.stop_event.timeout_wait()

    # Return from the third wait, which exits the thread.
    self.stop_event.set()
    self.t.join()
    self.assertEqual(3, interface.flush.call_count)

  def test_stop_stops(self):
    self.t.start()

    self.assertTrue(self.t.is_alive())

    self.t.stop()
    self.assertFalse(self.t.is_alive())
    self.assertEqual(1, interface.flush.call_count)

  def test_sleeps_for_exact_interval(self):
    self.t.start()

    # Flush takes 5 seconds.
    interface.flush.side_effect = functools.partial(self.increment_time, 5)

    self.assertEqual(60, self.stop_event.timeout_wait())
    self.assertEqual(55, self.stop_event.timeout_wait())
    self.assertEqual(55, self.stop_event.timeout_wait())

  def test_sleeps_for_minimum_zero_secs(self):
    self.t.start()

    # Flush takes 65 seconds.
    interface.flush.side_effect = functools.partial(self.increment_time, 65)

    self.assertEqual(60, self.stop_event.timeout_wait())
    self.assertEqual(0, self.stop_event.timeout_wait())
    self.assertEqual(0, self.stop_event.timeout_wait())
