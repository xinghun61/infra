# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import json
import os
import shutil
import signal
import tempfile
import time
import unittest

import mock

from infra.libs.service_utils import daemon
from infra.services.service_manager import service
from infra.services.service_manager import version_finder


class ServiceTest(unittest.TestCase):
  def setUp(self):
    self.state_directory = tempfile.mkdtemp()

    self.mock_sleep = mock.Mock(time.sleep)
    self.mock_time = mock.Mock(time.time)
    self.mock_time.return_value = 1234

    self.s = service.Service(
        self.state_directory,
        {
            'name': 'foo',
            'root_directory': '/rootdir',
            'tool': 'bar',
            'args': ['one', 'two'],
            'stop_time': 86,
        },
        time_fn=self.mock_time,
        sleep_fn=self.mock_sleep)
    self.s._read_starttime = self.mock_read_starttime = mock.Mock()
    self.mock_read_starttime.return_value = None

    self.mock_pipe = mock.patch('os.pipe').start()
    self.mock_fork = mock.patch('os.fork').start()
    self.mock_close = mock.patch('os.close').start()
    self.mock_exit = mock.patch('os._exit').start()
    self.mock_fdopen = mock.patch('os.fdopen').start()
    self.mock_waitpid = mock.patch('os.waitpid').start()
    self.mock_getpid = mock.patch('os.getpid').start()
    self.mock_execv = mock.patch('os.execv').start()
    self.mock_kill = mock.patch('os.kill').start()
    self.mock_become_daemon = mock.patch(
        'infra.libs.service_utils.daemon.become_daemon').start()
    self.mock_find_version = mock.patch(
        'infra.services.service_manager.version_finder.find_version').start()

  def tearDown(self):
    mock.patch.stopall()

    shutil.rmtree(self.state_directory)

  def _write_state(self, name, contents):
    with open(os.path.join(self.state_directory, name), 'w') as fh:
      fh.write(contents)

  def _all_writes(self, mock_file):
    return ''.join(call[0][0] for call in mock_file.write.call_args_list)

  def test_get_running_process_state(self):
    # No state file present.
    self.assertIs(None, self.s.get_running_process_state())
    self.assertFalse(self.s.is_running())

    # State file present but no /proc file.
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self.assertIs(None, self.s.get_running_process_state())
    self.assertFalse(self.s.is_running())

    # State file and /proc file present.
    self.mock_read_starttime.return_value = 5678
    self.assertEqual({'pid': 1234, 'starttime': 5678},
                     self.s.get_running_process_state())
    self.mock_read_starttime.assert_called_with(1234)
    self.assertTrue(self.s.is_running())

    # State file and /proc file present but different starttime.
    self.mock_read_starttime.return_value = 4242
    self.assertIs(None, self.s.get_running_process_state())
    self.assertFalse(self.s.is_running())

    # Invalid state file.
    self._write_state('foo', 'not valid json')
    self.mock_read_starttime.return_value = 5678
    self.assertIs(None, self.s.get_running_process_state())
    self.assertFalse(self.s.is_running())

  def test_start_already_running(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self.mock_read_starttime.return_value = 5678

    self.s.start()

    self.assertFalse(self.mock_fork.called)

  def test_start_parent(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 123

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.read.return_value = '{"pid": 777}'

    self.mock_waitpid.return_value = (None, 0)
    self.mock_read_starttime.return_value = 888

    self.mock_find_version.return_value = {'foo': 'bar'}

    self.s.start()

    self.assertTrue(self.mock_fork.called)
    self.assertTrue(self.mock_pipe.called)
    self.mock_close.assert_called_once_with(43)
    self.mock_fdopen.assert_called_once_with(42, 'r')
    self.mock_waitpid.assert_called_once_with(123, 0)
    self.mock_find_version.assert_called_once_with(self.s.config)

    with open(os.path.join(self.state_directory, 'foo')) as fh:
      self.assertEqual({
          'pid': 777,
          'starttime': 888,
          'version': {'foo': 'bar'}
      }, json.load(fh))

  def test_start_parent_child_exited(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 123

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.read.return_value = ''

    self.mock_waitpid.return_value = (None, 1)
    self.mock_read_starttime.return_value = 888

    with self.assertRaises(service.ServiceException):
      self.s.start()

  def test_start_parent_invalid_json(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 123

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.read.return_value = 'not valid json'

    self.mock_waitpid.return_value = (None, 0)
    self.mock_read_starttime.return_value = 888

    with self.assertRaises(service.ServiceException):
      self.s.start()

  def test_start_parent_no_proc_entry(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 123

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.read.return_value = '{"pid": 777}'

    self.mock_waitpid.return_value = (None, 0)

    with self.assertRaises(service.ServiceException):
      self.s.start()

  def test_start_child(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 0

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.fileno.return_value = 43

    self.mock_getpid.return_value = 555

    self.s.start()

    self.assertTrue(self.mock_fork.called)
    self.assertTrue(self.mock_pipe.called)
    self.assertEqual(mock.call(42), self.mock_close.call_args_list[0])
    self.mock_fdopen.assert_called_once_with(43, 'w')
    self.mock_become_daemon.assert_called_once_with(keep_fds={43})
    self.assertEqual('{"pid": 555}', self._all_writes(mock_pipe_object))
    mock_pipe_object.close.assert_called_once_with()
    self.mock_execv.assert_called_once_with('/rootdir/run.py', [
        '/rootdir/run.py',
        'bar',
        'one',
        'two',
    ])

  def test_stop_not_running(self):
    self.s.stop()
    self.assertFalse(self.mock_kill.called)

  def test_stop_sends_sig_term(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self.mock_read_starttime.return_value = 5678

    def delete_proc_entry(_duration):
      self.mock_read_starttime.return_value = None
    self.mock_sleep.side_effect = delete_proc_entry

    self.s.stop()

    self.mock_kill.assert_called_once_with(1234, signal.SIGTERM)
    self.assertFalse(os.path.exists(os.path.join(self.state_directory, 'foo')))

  def test_stop_sends_sig_kill(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self.mock_read_starttime.return_value = 5678

    current_time = [0]
    def sleep_impl(duration):
      current_time[0] += duration

    self.mock_sleep.side_effect = sleep_impl
    self.mock_time.side_effect = lambda: current_time[0]

    self.s.stop()

    self.assertEqual([
        mock.call(1234, signal.SIGTERM),
        mock.call(1234, signal.SIGKILL),
    ], self.mock_kill.call_args_list)
    self.assertAlmostEqual(86, current_time[0], places=0)  # 86 is the stop_time
    self.assertFalse(os.path.exists(os.path.join(self.state_directory, 'foo')))

  def test_stop_but_its_already_dead(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self.mock_read_starttime.return_value = 5678

    self.mock_kill.side_effect = OSError(errno.ESRCH, '')

    self.s.stop()

    self.mock_kill.assert_called_once_with(1234, signal.SIGTERM)
    self.assertFalse(os.path.exists(os.path.join(self.state_directory, 'foo')))

  def test_stop_with_another_kill_exception(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self.mock_read_starttime.return_value = 5678

    self.mock_kill.side_effect = OSError(errno.EPERM, '')

    with self.assertRaises(OSError):
      self.s.stop()

  def test_stop_but_another_process_recycled_the_pid(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self.mock_read_starttime.return_value = 5678

    def delete_proc_entry(_duration):
      self.mock_read_starttime.return_value = 9999
    self.mock_sleep.side_effect = delete_proc_entry

    self.s.stop()

    self.mock_kill.assert_called_once_with(1234, signal.SIGTERM)
    self.assertFalse(os.path.exists(os.path.join(self.state_directory, 'foo')))

  def test_has_version_changed_not_running(self):
    self.assertFalse(self.s.has_version_changed())
    self.assertFalse(self.mock_find_version.called)

  def test_has_version_changed_no(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678, "version": 1}')
    self.mock_read_starttime.return_value = 5678

    self.mock_find_version.return_value = 1
    self.assertFalse(self.s.has_version_changed())
    self.assertTrue(self.mock_find_version.called)

  def test_has_version_changed_yes(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678, "version": 1}')
    self.mock_read_starttime.return_value = 5678

    self.mock_find_version.return_value = 2
    self.assertTrue(self.s.has_version_changed())
    self.assertTrue(self.mock_find_version.called)
