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


class ServiceTest(unittest.TestCase):
  def setUp(self):
    self.state_directory = tempfile.mkdtemp()
    self.proc_directory = tempfile.mkdtemp()

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
        sleep_fn=self.mock_sleep,
        proc_directory=self.proc_directory)

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

  def tearDown(self):
    mock.patch.stopall()

    shutil.rmtree(self.state_directory)
    shutil.rmtree(self.proc_directory)

  def _write_starttime(self, pid, starttime):
    try:
      os.mkdir(os.path.join(self.proc_directory, str(pid)))
    except OSError:
      pass

    with open(os.path.join(self.proc_directory, str(pid), "stat"), 'w') as fh:
      fh.write(' '.join(
          [str(x) for x in range(21) + [starttime] + range(22, 30)]))

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
    self._write_starttime(1234, 5678)
    self.assertEqual({'pid': 1234, 'starttime': 5678},
                     self.s.get_running_process_state())
    self.assertTrue(self.s.is_running())

    # State file and /proc file present but different starttime.
    self._write_starttime(1234, 4242)
    self.assertIs(None, self.s.get_running_process_state())
    self.assertFalse(self.s.is_running())

    # Invalid state file.
    self._write_state('foo', 'not valid json')
    self._write_starttime(1234, 5678)
    self.assertIs(None, self.s.get_running_process_state())
    self.assertFalse(self.s.is_running())

  def test_start_already_running(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self._write_starttime(1234, 5678)

    self.s.start()

    self.assertFalse(self.mock_fork.called)

  def test_start_parent(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 123

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.read.return_value = '{"pid": 777}'

    self.mock_waitpid.return_value = (None, 0)
    self._write_starttime(777, 888)

    self.s.start()

    self.assertTrue(self.mock_fork.called)
    self.assertTrue(self.mock_pipe.called)
    self.mock_close.assert_called_once_with(43)
    self.mock_fdopen.assert_called_once_with(42, 'r')
    self.mock_waitpid.assert_called_once_with(123, 0)

    with open(os.path.join(self.state_directory, 'foo')) as fh:
      self.assertEqual({
          'pid': 777,
          'starttime': 888,
      }, json.load(fh))

  def test_start_parent_child_exited(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 123

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.read.return_value = ''

    self.mock_waitpid.return_value = (None, 1)
    self._write_starttime(777, 888)

    with self.assertRaises(service.ServiceException):
      self.s.start()

  def test_start_parent_invalid_json(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 123

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.read.return_value = 'not valid json'

    self.mock_waitpid.return_value = (None, 0)
    self._write_starttime(777, 888)

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
    self._write_starttime(1234, 5678)

    def delete_proc_entry(_duration):
      os.unlink(os.path.join(self.proc_directory, '1234', 'stat'))
    self.mock_sleep.side_effect = delete_proc_entry

    self.s.stop()

    self.mock_kill.assert_called_once_with(1234, signal.SIGTERM)
    self.assertFalse(os.path.exists(os.path.join(self.state_directory, 'foo')))

  def test_stop_sends_sig_kill(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self._write_starttime(1234, 5678)

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
    self._write_starttime(1234, 5678)

    self.mock_kill.side_effect = OSError(errno.ESRCH, '')

    self.s.stop()

    self.mock_kill.assert_called_once_with(1234, signal.SIGTERM)
    self.assertFalse(os.path.exists(os.path.join(self.state_directory, 'foo')))

  def test_stop_with_another_kill_exception(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self._write_starttime(1234, 5678)

    self.mock_kill.side_effect = OSError(errno.EPERM, '')

    with self.assertRaises(OSError):
      self.s.stop()

  def test_stop_but_another_process_recycled_the_pid(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self._write_starttime(1234, 5678)

    def delete_proc_entry(_duration):
      self._write_starttime(1234, 9999)
    self.mock_sleep.side_effect = delete_proc_entry

    self.s.stop()

    self.mock_kill.assert_called_once_with(1234, signal.SIGTERM)
    self.assertFalse(os.path.exists(os.path.join(self.state_directory, 'foo')))
