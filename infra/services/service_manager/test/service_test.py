# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import json
import os
import shutil
import signal
import sys
import tempfile
import time
import unittest

import mock

from infra.libs.service_utils import daemon
from infra.services.service_manager import service
from infra.services.service_manager import version_finder
import infra_libs


class TestBase(unittest.TestCase):
  def setUp(self):
    self.state_directory = tempfile.mkdtemp()

    self.mock_getpid = mock.patch('os.getpid').start()
    self.mock_getpid.return_value = 7
    self.mock_find_version = mock.patch(
        'infra.services.service_manager.version_finder.find_version').start()

    self.mock_read_starttime = (mock.patch(
        'infra.services.service_manager.service._read_starttime')
        .start())
    self.mock_read_starttime.return_value = None

  def tearDown(self):
    mock.patch.stopall()

    infra_libs.rmtree(self.state_directory)

  def _state_filename(self, name):
    return os.path.join(self.state_directory, name)

  def _write_state(self, name, contents):
    with open(self._state_filename(name), 'w') as fh:
      fh.write(contents)

  def _all_writes(self, mock_file):
    return ''.join(call[0][0] for call in mock_file.write.call_args_list)


class ProcessStateTest(TestBase):
  def test_from_file(self):
    path = self._state_filename('foo')

    # File doesn't exist.
    with self.assertRaises(service.StateFileNotFound):
      service.ProcessState.from_file(path)

    if sys.platform != 'win32':  # pragma: no cover
      # State file present but not readable.
      self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
      os.chmod(path, 0)
      with self.assertRaises(service.StateFileOpenError):
        service.ProcessState.from_file(path)
      os.unlink(path)

    # State file present but no /proc file.
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    with self.assertRaises(service.ProcessNotRunning):
      service.ProcessState.from_file(path)

    # State file and /proc file present.
    self.mock_read_starttime.return_value = 5678
    state = service.ProcessState.from_file(path)
    self.assertEqual(1234, state.pid)
    self.assertEqual(5678, state.starttime)

    # State file and /proc file present but different starttime.
    self.mock_read_starttime.return_value = 4242
    with self.assertRaises(service.ProcessHasDifferentStartTime):
      service.ProcessState.from_file(path)

    # Invalid state file.
    self._write_state('foo', 'not valid json')
    self.mock_read_starttime.return_value = 5678
    with self.assertRaises(service.StateFileParseError):
      service.ProcessState.from_file(path)

  def test_from_pid(self):
    # Not running.
    with self.assertRaises(service.ProcessNotRunning):
       service.ProcessState.from_pid(1234)

    # Running.
    self.mock_read_starttime.return_value = 5678
    state = service.ProcessState.from_pid(1234)
    self.assertEqual(1234, state.pid)
    self.assertEqual(5678, state.starttime)


class ServiceTest(TestBase):
  def setUp(self):
    super(ServiceTest, self).setUp()

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
            'stop_time': '86',
        },
        None,
        time_fn=self.mock_time,
        sleep_fn=self.mock_sleep)

    if sys.platform == 'win32':  # pragma: no cover
      self.mock_fork = mock.Mock()
    else:
      self.mock_fork = mock.patch('os.fork').start()

    self.mock_pipe = mock.patch('os.pipe').start()
    self.mock_close = mock.patch('os.close').start()
    self.mock_exit = mock.patch('os._exit').start()
    self.mock_fdopen = mock.patch('os.fdopen').start()
    self.mock_waitpid = mock.patch('os.waitpid').start()
    self.mock_execv = mock.patch('os.execv').start()
    self.mock_kill = mock.patch('os.kill').start()
    self.mock_become_daemon = mock.patch(
        'infra.libs.service_utils.daemon.become_daemon').start()
    self.mock_close_all_fds = mock.patch(
        'infra.libs.service_utils.daemon.close_all_fds').start()

  def test_start_already_running(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self.mock_read_starttime.return_value = 5678

    self.s.start()

    self.assertFalse(self.mock_fork.called)

  @unittest.skipIf(sys.platform == 'win32', 'windows')
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

    with open(self._state_filename('foo')) as fh:
      self.assertEqual({
          'pid': 777,
          'starttime': 888,
          'version': {'foo': 'bar'},
          'args': ['one', 'two'],
      }, json.load(fh))

  @unittest.skipIf(sys.platform == 'win32', 'windows')
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

  @unittest.skipIf(sys.platform == 'win32', 'windows')
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

  @unittest.skipIf(sys.platform == 'win32', 'windows')
  def test_start_parent_no_proc_entry(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 123

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.read.return_value = '{"pid": 777}'

    self.mock_waitpid.return_value = (None, 0)

    with self.assertRaises(service.ServiceException):
      self.s.start()

  @unittest.skipIf(sys.platform == 'win32', 'windows')
  def test_start_child(self):
    self.mock_pipe.return_value = (42, 43)
    self.mock_fork.return_value = 0

    mock_pipe_object = mock.Mock(file)
    self.mock_fdopen.return_value = mock_pipe_object
    mock_pipe_object.fileno.return_value = 43

    self.mock_getpid.return_value = 555

    # Skip the end of Process.start that assumes it's still the parent process.
    self.mock_exit.side_effect = SystemExit
    with self.assertRaises(SystemExit):
      self.s.start()

    self.assertTrue(self.mock_fork.called)
    self.assertTrue(self.mock_pipe.called)
    self.assertEqual(mock.call(42), self.mock_close.call_args_list[0])
    self.mock_fdopen.assert_called_once_with(43, 'w')
    self.mock_become_daemon.assert_called_once_with(keep_fds=True)
    self.mock_close_all_fds.assert_called_once_with(keep_fds={1, 2})
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
    self.assertFalse(os.path.exists(self._state_filename('foo')))

  @unittest.skipIf(sys.platform == 'win32', 'windows')
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
    self.assertFalse(os.path.exists(self._state_filename('foo')))

  def test_stop_but_its_already_dead(self):
    self._write_state('foo', '{"pid": 1234, "starttime": 5678}')
    self.mock_read_starttime.return_value = 5678

    self.mock_kill.side_effect = OSError(errno.ESRCH, '')

    self.s.stop()

    self.mock_kill.assert_called_once_with(1234, signal.SIGTERM)
    self.assertFalse(os.path.exists(self._state_filename('foo')))

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
    self.assertFalse(os.path.exists(self._state_filename('foo')))

  def test_has_version_changed_not_running(self):
    state = service.ProcessState()
    self.assertFalse(self.s.has_version_changed(state))
    self.assertFalse(self.mock_find_version.called)

  def test_has_version_changed_no(self):
    state = service.ProcessState(pid=1234, starttime=5678, version=1)

    self.mock_find_version.return_value = 1
    self.assertFalse(self.s.has_version_changed(state))
    self.assertTrue(self.mock_find_version.called)

  def test_has_version_changed_yes(self):
    state = service.ProcessState(pid=1234, starttime=5678, version=1)

    self.mock_find_version.return_value = 2
    self.assertTrue(self.s.has_version_changed(state))
    self.assertTrue(self.mock_find_version.called)

  def test_has_version_changed_not_written(self):
    state = service.ProcessState(pid=1234, starttime=5678)

    self.mock_find_version.return_value = 2
    self.assertFalse(self.s.has_version_changed(state))

  def test_has_args_changed_not_running(self):
    state = service.ProcessState()
    self.assertFalse(self.s.has_args_changed(state))

  def test_has_args_changed_no(self):
    state = service.ProcessState(
        pid=1234, starttime=5678, version=1, args=['one', 'two'])
    self.assertFalse(self.s.has_args_changed(state))

  def test_has_args_changed_yes(self):
    state = service.ProcessState(
        pid=1234, starttime=5678, version=1, args=['one'])
    self.assertTrue(self.s.has_args_changed(state))

  def test_has_args_changed_not_written(self):
    state = service.ProcessState(pid=1234, starttime=5678, version=1)
    self.assertFalse(self.s.has_args_changed(state))

  def test_cloudtail_args(self):
    self.assertIsNone(self.s.cloudtail_args)

    self.s = service.Service(
        self.state_directory,
        {
            'name': 'foo',
            'root_directory': '/rootdir',
            'tool': 'bar',
            'args': ['one', 'two'],
            'stop_time': '86',
        },
        '/cloudtail',
        time_fn=self.mock_time,
        sleep_fn=self.mock_sleep)

    self.assertIn('/cloudtail', self.s.cloudtail_args)
    self.assertIn('foo', self.s.cloudtail_args)


class ProcessCreatorTest(unittest.TestCase):
  def setUp(self):
    self.mock_popen = mock.patch('subprocess.Popen').start()
    self.mock_service = mock.create_autospec('service.Service', instance=True)
    self.mock_service.name = 'foo'
    self.c = service.ProcessCreator(self.mock_service)

  def tearDown(self):
    mock.patch.stopall()

  def test_open_output_fh_no_cloudtail(self):
    self.mock_service.cloudtail_args = None
    fh = self.c._open_output_fh({'foo': 'bar'})
    try:
      self.assertFalse(self.mock_popen.called)
      self.assertEqual(os.devnull, fh.name)
    finally:
      fh.close()

  def test_open_output_fh(self):
    self.mock_service.cloudtail_args = [1, 2, 3]
    self.mock_popen.return_value.pid = 1234
    fh = self.c._open_output_fh({'foo': 'bar'})
    try:
      self.assertEquals(1, self.mock_popen.call_count)
      self.assertEquals([1, 2, 3], self.mock_popen.call_args[0][0])
      kwargs = self.mock_popen.call_args[1]
      self.assertIn('foo', kwargs)
      self.assertIn('stdin', kwargs)
      self.assertIn('stdout', kwargs)
      self.assertIn('stderr', kwargs)

      self.assertEquals(os.devnull, kwargs['stdout'].name)
      self.assertEquals(os.devnull, kwargs['stderr'].name)
      self.assertEquals('<fdopen>', fh.name)

      # Clean up the write end of the pipe.
      kwargs['stdout'].close()
    finally:
      fh.close()

  def test_open_output_fh_not_found(self):
    self.mock_service.cloudtail_args = [1, 2, 3]
    self.mock_popen.side_effect = OSError()
    fh = self.c._open_output_fh({'foo': 'bar'})
    try:
      self.assertEquals(1, self.mock_popen.call_count)
      kwargs = self.mock_popen.call_args[1]
      self.assertEqual(os.devnull, fh.name)

      # Clean up the write end of the pipe.
      kwargs['stdout'].close()
    finally:
      fh.close()


class OwnServiceTest(TestBase):
  def setUp(self):
    super(OwnServiceTest, self).setUp()

    self.root_directory = tempfile.mkdtemp()

    self.s = service.OwnService(
        self.state_directory,
        self.root_directory)

    self.mock_flock = mock.patch(
        'infra.libs.service_utils.daemon.flock').start()

  def tearDown(self):
    super(OwnServiceTest, self).tearDown()
    infra_libs.rmtree(self.root_directory)

  def test_start_locked(self):
    self.mock_flock.side_effect = daemon.LockAlreadyLocked

    self.assertFalse(self.s.start())
    with self.assertRaises(service.ProcessStateError):
      self.s.get_running_process_state()

  def test_start_running(self):
    self.mock_getpid.return_value = 1234
    self._write_state('service_manager', '{"pid": 1234, "starttime": 5678}')
    self.mock_read_starttime.return_value = 5678

    self.assertEquals(1234, self.s.get_running_process_state().pid)
    self.assertFalse(self.s.start())
    self.assertEquals(1234, self.s.get_running_process_state().pid)

  def test_start(self):
    self.mock_getpid.return_value = 1234
    self.mock_find_version.return_value = 42
    self.mock_read_starttime.return_value = 5678

    with self.assertRaises(service.ProcessStateError):
      self.s.get_running_process_state()
    self.assertTrue(self.s.start())

    state = self.s.get_running_process_state()
    self.assertEqual(1234, state.pid)
    self.assertEqual(5678, state.starttime)
    self.assertEqual(42, state.version)
    self.assertEqual([], state.args)

  def test_stop(self):
    with self.assertRaises(NotImplementedError):
      self.s.stop()
