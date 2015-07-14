# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import threading
import unittest

import mock

from infra.services.service_manager import service
from infra.services.service_manager import service_thread


class FakeCondition(object):
  def __init__(self):
    self.notify_called = False
    self.wait_timeout = None

    self._wait_enter_semaphore = threading.Semaphore(0)
    self._wait_exit_semaphore = threading.Semaphore(0)

  def wait(self, timeout):
    self.wait_timeout = timeout
    self._wait_enter_semaphore.release()
    self._wait_exit_semaphore.acquire()

  def notify(self):
    self.notify_called = True

  def start(self):
    self._wait_enter_semaphore.acquire()

  def next(self, blocking=True):
    self.notify_called = False
    self._wait_exit_semaphore.release()
    if blocking:
      self._wait_enter_semaphore.acquire()

  def __enter__(self):
    pass

  def __exit__(self, _exc_type, _exc_value, _traceback):
    pass


class ServiceThreadTest(unittest.TestCase):
  def setUp(self):
    service_thread.ServiceThread.failures.reset()
    service_thread.ServiceThread.reconfigs.reset()
    service_thread.ServiceThread.upgrades.reset()

    self.mock_service_ctor = mock.patch(
        'infra.services.service_manager.service.Service').start()
    self.mock_service = self.mock_service_ctor.return_value
    self.mock_service.name = 'foo'

    config = {'name': 'foo'}
    self.condition = FakeCondition()
    self.t = service_thread.ServiceThread(
        10, '/foo', config, wait_condition=self.condition)

    self.mock_service_ctor.assert_called_once_with('/foo', config)

  def tearDown(self):
    if self.t.is_alive():
      self.t.stop(join=False)
      self.condition.next(blocking=False)
      self.t.join()

    mock.patch.stopall()

  def test_run_and_exit(self):
    self.t.start()
    self.condition.start()

    # The timeout is the same as specified in the constructor.
    self.assertEqual(10, self.condition.wait_timeout)
    self.assertFalse(self.condition.notify_called)

    # Calling stop wakes up the thread.
    self.t.stop(join=False)
    self.assertTrue(self.condition.notify_called)
    self.condition.next(blocking=False)

    # And then makes it exit.
    self.t.join()

  def test_no_action_by_default(self):
    self.t.start()
    self.condition.start()
    self.condition.next()

    self.assertFalse(self.mock_service.start.called)
    self.assertFalse(self.mock_service.stop.called)

  def test_start(self):
    self.t.start()
    self.condition.start()

    self.mock_service.is_running.return_value = False

    self.t.start_service()
    self.assertTrue(self.condition.notify_called)
    self.condition.next()

    self.mock_service.start.assert_called_once_with()

  def test_restart_after_failure(self):
    self.t.start()
    self.condition.start()

    self.assertEqual(0, self.t.failures.get({'service': 'foo'}))

    self.mock_service.is_running.return_value = False

    self.t.start_service()
    self.assertTrue(self.condition.notify_called)
    self.condition.next()

    self.mock_service.start.assert_called_once_with()
    self.assertEqual(0, self.t.failures.get({'service': 'foo'}))

    self.condition.next()
    self.assertEqual(2, self.mock_service.start.call_count)
    self.assertEqual(1, self.t.failures.get({'service': 'foo'}))

    self.condition.next()
    self.assertEqual(3, self.mock_service.start.call_count)
    self.assertEqual(2, self.t.failures.get({'service': 'foo'}))

    self.mock_service.is_running.return_value = True

    self.condition.next()
    self.assertEqual(2, self.t.failures.get({'service': 'foo'}))

  def test_restart_after_upgrade(self):
    self.t.start()
    self.condition.start()

    self.assertEqual(0, self.t.upgrades.get({'service': 'foo'}))

    self.mock_service.is_running.return_value = False
    self.mock_service.has_version_changed.return_value = False
    self.mock_service.has_args_changed.return_value = False

    self.t.start_service()
    self.assertTrue(self.condition.notify_called)
    self.condition.next()

    self.assertEqual(0, self.mock_service.stop.call_count)
    self.assertEqual(1, self.mock_service.start.call_count)
    self.assertEqual(0, self.t.upgrades.get({'service': 'foo'}))

    self.mock_service.is_running.return_value = True

    self.condition.next()
    self.assertEqual(0, self.mock_service.stop.call_count)
    self.assertEqual(2, self.mock_service.start.call_count)
    self.assertEqual(0, self.t.upgrades.get({'service': 'foo'}))

    self.mock_service.has_version_changed.return_value = True

    self.condition.next()
    self.assertEqual(1, self.mock_service.stop.call_count)
    self.assertEqual(3, self.mock_service.start.call_count)
    self.assertEqual(1, self.t.upgrades.get({'service': 'foo'}))

  def test_stop(self):
    self.t.start()
    self.condition.start()

    self.t.stop_service()
    self.assertTrue(self.condition.notify_called)
    self.condition.next()

    self.mock_service.stop.assert_called_with()

  def test_reconfig(self):
    self.t.start()
    self.condition.start()

    self.assertEqual(0, self.t.reconfigs.get({'service': 'foo'}))

    new_config = {'name': 'bar'}
    new_service = mock.Mock()
    self.mock_service_ctor.return_value = new_service

    self.t.restart_with_new_config(new_config)
    self.assertTrue(self.condition.notify_called)
    self.condition.next()

    self.assertEqual(1, self.t.reconfigs.get({'service': 'foo'}))
    self.mock_service.stop.assert_called_once_with()
    self.mock_service_ctor.assert_called_with('/foo', new_config)
    new_service.start.assert_called_once_with()

  def test_new_args_on_startup(self):
    self.t.start()
    self.condition.start()

    self.assertEqual(0, self.t.reconfigs.get({'service': 'foo'}))

    self.mock_service.is_running.return_value = True
    self.mock_service.has_version_changed.return_value = False
    self.mock_service.has_args_changed.return_value = True
    self.t.start_service()
    self.condition.next()

    self.assertEqual(1, self.t.reconfigs.get({'service': 'foo'}))
    self.mock_service.stop.assert_called_once_with()
    self.mock_service.start.assert_called_once_with()

  def test_start_raises(self):
    self.t.start()
    self.condition.start()

    self.mock_service.start.side_effect = Exception()

    self.t.start_service()
    self.assertTrue(self.condition.notify_called)
    self.condition.next()

    self.mock_service.start.assert_called_once_with()

    # The loop should continue.
    self.condition.next()
