# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import collections
import fcntl
import os
import sys
import unittest

from testing_support import auto_stub
from infra.libs.service_utils import daemon


Stat = collections.namedtuple('Stat', ['st_ino'])


class TestFlock(auto_stub.TestCase):
  def setUp(self):
    super(TestFlock, self).setUp()

    # daemon.flock() only works on linux/osx, so set 'linux' here if we're
    # testing in windows. The OS calls are mocked so it will still work. If
    # windows support is added, remove this mock entirely.
    self.mock(sys, 'platform', 'linux2')

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
  def setUp(self):
    super(TestTimeout, self).setUp()

    # daemon.add_timeout() only works on linux, so set 'linux' here if we're
    # testing in windows/osx. If windows or osx support is added, change
    # accordingly.
    self.mock(sys, 'platform', 'linux2')

  def testAddTimeout(self):
    self.assertEqual(
        ['timeout', '600', 'echo', 'hey'],
        daemon.add_timeout(['echo', 'hey'], 600))
