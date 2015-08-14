# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import collections
import errno
import os
import sys
import unittest

try:
  import fcntl
except ImportError:  # pragma: no cover
  # Doesn't exist on Windows. See also crbug.com/515704.
  pass

from testing_support import auto_stub
from infra.libs.service_utils import daemon

import mock


Stat = collections.namedtuple('Stat', ['st_ino'])


class TestFlock(auto_stub.TestCase):
  @unittest.skipIf(sys.platform == 'win32', 'Requires not windows')
  def setUp(self):
    super(TestFlock, self).setUp()

  @contextlib.contextmanager
  def _assert_reached(self):
    reached = {'yup': False}
    yield reached
    self.assertTrue(reached['yup'])

  def _mock_basic_fs_calls(self):
    """Mocks os.open, os.close as well as os.fstat."""
    def _noop_handler(*_args, **_kwargs):
      return 1

    def _noop_os_close(*_args, **_kwargs):
      pass

    def _noop_fstat(*_args, **_kwargs):
      return Stat(st_ino=45678)

    self.mock(os, 'open', _noop_handler)
    self.mock(os, 'close', _noop_os_close)
    self.mock(os, 'fstat', _noop_fstat)

  def _set_lock_status(self, success=True):
    """Mocks os.fcntl and whether the mock succeeds or not."""
    def _lock_status(_fd, flags, **_kwargs):
      if flags != fcntl.LOCK_UN:  # We don't care if unlock fails.
        if not success:
          raise IOError('Couldn\'t get lock.')

    self.mock(fcntl, 'lockf', _lock_status)

  def _set_stat_status(self, success=True, matching=True):
    """Mocks os.stat, sets its success and if st_ino matches os.fstat mock."""
    def _stat_handler(*_args, **_kwargs):
      if not success:
        raise OSError('Not found.')
      if matching:
        return Stat(st_ino=45678)
      return Stat(st_ino=67890)

    self.mock(os, 'stat', _stat_handler)

  def _set_unlink_status(self, success=True):
    """Mocks os.unlink and sets whether it succeeds or not."""
    def _unlink_handler(*_args, **_kwargs):
      if not success:
        raise OSError('Not found.')

    self.mock(os, 'unlink', _unlink_handler)

  #### Tests.

  def testGetLock(self):
    self._mock_basic_fs_calls()
    self._set_lock_status()
    self._set_stat_status()
    self._set_unlink_status()
    with self._assert_reached() as reached:
      with daemon.flock('bogus'):
        reached['yup'] = True

  def testDontGetLock(self):
    self._mock_basic_fs_calls()
    self._set_lock_status(success=False)
    self._set_stat_status()
    self._set_unlink_status()
    with self.assertRaises(daemon.LockAlreadyLocked):
      with daemon.flock('bogus'):
        # Should never reach this.
        # pylint: disable=redundant-unittest-assert
        self.assertTrue(False)  # pragma: no cover

  def testFileDeletedAfterLockAcquired(self):
    """Test that we abort if we acquire a lock but the file has been deleted."""
    self._mock_basic_fs_calls()
    self._set_lock_status()
    self._set_stat_status(success=False)
    self._set_unlink_status()
    with self.assertRaises(daemon.LockAlreadyLocked):
      with daemon.flock('bogus'):
        # Should never reach this.
        # pylint: disable=redundant-unittest-assert
        self.assertTrue(False)  # pragma: no cover

  def testLockfileRecreated(self):
    """Test that we abort if a new lockfile is created under us."""
    self._mock_basic_fs_calls()
    self._set_lock_status()
    self._set_stat_status(matching=False)
    self._set_unlink_status()
    with self.assertRaises(daemon.LockAlreadyLocked):
      with daemon.flock('bogus'):
        # Should never reach this.
        # pylint: disable=redundant-unittest-assert
        self.assertTrue(False)  # pragma: no cover

  def testDeleteWhenDone(self):
    """Test that we delete the lockfile when we're done."""
    data = {'count': 0}
    def _mock_unlink(*_args, **_kwargs):
      data['count'] += 1
    self.mock(os, 'unlink', _mock_unlink)
    self._mock_basic_fs_calls()
    self._set_lock_status()
    self._set_stat_status()
    with self._assert_reached() as reached:
      with daemon.flock('bogus'):
        reached['yup'] = True
    self.assertEqual(data['count'], 1)


  def testUnlinkFailureDoesntBreak(self):
    """Test that a failing unlink doesn't break us."""
    self._mock_basic_fs_calls()
    self._set_lock_status()
    self._set_stat_status()
    self._set_unlink_status(success=False)
    with self._assert_reached() as reached:
      with daemon.flock('bogus'):
        reached['yup'] = True


class TestTimeout(auto_stub.TestCase):
  @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires linux')
  def setUp(self):
    super(TestTimeout, self).setUp()

  def testAddTimeout(self):
    self.assertEqual(
        ['timeout', '600', 'echo', 'hey'],
        daemon.add_timeout(['echo', 'hey'], 600))


@mock.patch('os.fork', return_value=0)
@mock.patch('os.setsid')
@mock.patch('os.close')
@mock.patch('os.open')
@mock.patch('os.dup2')
@mock.patch('os.chdir')
@mock.patch('os._exit')
class TestBecomeDaemon(unittest.TestCase):
  @unittest.skipIf(sys.platform == 'win32', 'Requires not windows')
  def setUp(self):
    super(TestBecomeDaemon, self).setUp()

  def testClosesFds(self, _mock_exit, _mock_chdir, _mock_dup2, _mock_open,
                    mock_close, _mock_setsid, _mock_fork):
    daemon.become_daemon()

    self.assertEqual(2048, mock_close.call_count)
    self.assertEqual([((i,),) for i in reversed(range(2048))],
                     mock_close.call_args_list)

  def testClosesFdWithExceptions(self, _mock_exit, _mock_chdir, _mock_dup2,
                                 _mock_open, mock_close, _mock_setsid,
                                 _mock_fork):
    daemon.become_daemon(keep_fds={42})

    self.assertEqual(2047, mock_close.call_count)
    self.assertEqual([((i,),) for i in reversed(range(2048)) if i != 42],
                     mock_close.call_args_list)

  def testClosesInvalidFds(self, _mock_exit, _mock_chdir, _mock_dup2,
                           _mock_open, mock_close, _mock_setsid, _mock_fork):
    mock_close.side_effect = EnvironmentError(errno.EIO, '')
    with self.assertRaises(EnvironmentError):
      daemon.become_daemon()

    mock_close.side_effect = EnvironmentError(errno.EBADF, '')
    daemon.become_daemon()

  def testOpensDevNull(self, _mock_exit, _mock_chdir, mock_dup2, mock_open,
                       _mock_close, _mock_setsid, _mock_fork):
    handle = object()
    mock_open.return_value = handle

    daemon.become_daemon()

    self.assertEqual([
        ((handle, 0),),
        ((handle, 1),),
        ((handle, 2),),
    ], mock_dup2.call_args_list)

  def testChangesToRoot(self, _mock_exit, mock_chdir, _mock_dup2, _mock_open,
                        _mock_close, _mock_setsid, _mock_fork):
    daemon.become_daemon()
    mock_chdir.assert_called_with('/')

  def testForkExitsParent(self, mock_exit, _mock_chdir, _mock_dup2, _mock_open,
                          _mock_close, _mock_setsid, mock_fork):
    mock_fork.return_value = 0
    daemon.become_daemon()
    self.assertFalse(mock_exit.called)

    mock_fork.return_value = 123
    daemon.become_daemon()
    self.assertTrue(mock_exit.called)
