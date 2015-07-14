# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os.path
import shutil
import tempfile
import unittest

import mock

from infra.services.service_manager import config_watcher
from infra.services.service_manager import service
from infra.services.service_manager import service_thread


class ConfigWatcherTest(unittest.TestCase):
  def setUp(self):
    self.config_directory = tempfile.mkdtemp()

    self.mock_sleep = mock.Mock()

    self.mock_ownservice_ctor = mock.patch(
        'infra.services.service_manager.service.OwnService').start()
    self.mock_thread_ctor = mock.patch(
        'infra.services.service_manager.service_thread.ServiceThread').start()
    self.mock_thread = self.mock_thread_ctor.return_value
    self.mock_ownservice = self.mock_ownservice_ctor.return_value
    self.mock_ownservice.start.return_value = True
    self.mock_ownservice.has_version_changed.return_value = False

    self.cw = config_watcher.ConfigWatcher(
        self.config_directory,
        42,
        43,
        '/state',
        '/rootdir',
        sleep_fn=self.mock_sleep)

  def tearDown(self):
    mock.patch.stopall()

    shutil.rmtree(self.config_directory)

  def _set_config(self, name, contents, mtime=None):
    filename = os.path.join(self.config_directory, name)
    with open(filename, 'w') as fh:
      fh.write(contents)
    if mtime is not None:
      os.utime(filename, (mtime, mtime))

  def _remove_config(self, name):
    os.unlink(os.path.join(self.config_directory, name))

  def test_already_running(self):
    self.mock_ownservice.start.return_value = False

    self.cw.run()
    self.assertFalse(self.mock_sleep.called)

  def test_version_changed(self):
    self.mock_ownservice.has_version_changed.return_value = True

    self.cw._iteration()
    self.assertTrue(self.cw._stop)

  def test_add(self):
    self._set_config('foo.json', '{"name": "foo"}')

    self.cw._iteration()

    self.mock_thread_ctor.assert_called_once_with(43, '/state', {'name': 'foo'})
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

  def test_add_invalid_json(self):
    self._set_config('foo.json', '{"name": ')

    self.cw._iteration()

    self.assertFalse(self.mock_thread_ctor.called)

  def test_add_filename_does_not_match_name(self):
    self._set_config('foo.json', '{"name": "bar"}')

    self.cw._iteration()

    self.mock_thread_ctor.assert_called_once_with(43, '/state', {'name': 'bar'})
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

  def test_add_duplicate_name(self):
    self._set_config('foo.json', '{"name": "foo"}')
    self.cw._iteration()
    self.assertEqual(1, self.mock_thread_ctor.call_count)

    self._set_config('bar.json', '{"name": "foo"}')
    self.cw._iteration()
    self.assertEqual(1, self.mock_thread_ctor.call_count)

  def test_change(self):
    self._set_config('foo.json', '{"name": "foo"}', 100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(43, '/state', {'name': 'foo'})

    self._set_config('foo.json', '{"name": "foo", "args": [1, 2, 3]}', 200)

    self.cw._iteration()
    self.mock_thread.restart_with_new_config.assert_called_once_with(
        {'name': 'foo', 'args': [1, 2, 3]})

  def test_change_duplicate_name(self):
    self._set_config('foo.json', '{"name": "foo"}', 100)
    self.cw._iteration()
    self.assertEqual(1, self.mock_thread_ctor.call_count)
    self.assertEqual(1, self.mock_thread.start_service.call_count)
    self.assertEqual(0, self.mock_thread.stop_service.call_count)

    self._set_config('bar.json', '{"name": "bar"}', 200)
    self.cw._iteration()
    self.assertEqual(2, self.mock_thread_ctor.call_count)
    self.assertEqual(2, self.mock_thread.start_service.call_count)
    self.assertEqual(0, self.mock_thread.stop_service.call_count)

    self._set_config('bar.json', '{"name": "foo"}', 300)
    self.cw._iteration()
    self.assertEqual(2, self.mock_thread_ctor.call_count)
    self.assertEqual(2, self.mock_thread.start_service.call_count)
    self.assertEqual(1, self.mock_thread.stop_service.call_count)

  def test_add_bad_config_then_change(self):
    self._set_config('foo.json', '{"name": ', 100)

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

    self._set_config('foo.json', '{"name": "foo"}', 200)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(43, '/state', {'name': 'foo'})
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

  def test_add_bad_config_then_remove(self):
    self._set_config('foo.json', '{"name": ', 100)

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

    self._remove_config('foo.json')

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

  def test_add_good_config_then_make_bad(self):
    self._set_config('foo.json', '{"name": "foo"}', 100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(43, '/state', {'name': 'foo'})
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

    self._set_config('foo.json', '{"name": ', 200)

    self.cw._iteration()
    self.mock_thread.stop_service.assert_called_once_with()

  def test_add_bad_config_then_touch(self):
    self._set_config('foo.json', '{"name": }', 100)

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

    self._set_config('foo.json', '{"name": ', 200)

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

  def test_remove_config(self):
    self._set_config('foo.json', '{"name": "foo"}', 100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(43, '/state', {'name': 'foo'})
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

    self._remove_config('foo.json')

    self.cw._iteration()
    self.mock_thread.stop_service.assert_called_once_with()

  def test_remove_and_readd_config(self):
    self._set_config('foo.json', '{"name": "foo"}', 100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(43, '/state', {'name': 'foo'})
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

    self._remove_config('foo.json')

    self.cw._iteration()
    self.mock_thread.stop_service.assert_called_once_with()

    self._set_config('foo.json', '{"name": "foo"}', 100)

    self.cw._iteration()
    self.assertEqual(1, self.mock_thread_ctor.call_count)
    self.assertEqual(1, self.mock_thread.start_service.call_count)
    self.mock_thread.restart_with_new_config.assert_called_once_with(
        {'name': 'foo'})

  def test_run_stop(self):
    self._set_config('foo.json', '{"name": "foo"}', 100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(43, '/state', {'name': 'foo'})

    def sleep_impl(_duration):
      self.cw.stop()
    self.mock_sleep.side_effect = sleep_impl

    self.cw.run()

    self.mock_sleep.assert_called_once_with(42)
    self.mock_thread.stop.assert_called_once_with()
    self.assertFalse(self.mock_thread.stop_service.called)

  def test_run_stop_bad_config(self):
    self._set_config('foo.json', '{"name": ')

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

    def sleep_impl(_duration):
      self.cw.stop()
    self.mock_sleep.side_effect = sleep_impl

    self.cw.run()

    self.mock_sleep.assert_called_once_with(42)
    self.assertFalse(self.mock_thread_ctor.called)
