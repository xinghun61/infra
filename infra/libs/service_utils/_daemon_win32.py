# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Locking, timeout, and other process management functions."""

import contextlib
import ctypes
import ctypes.wintypes
import os
import tempfile

GENERIC_WRITE = 0x40000000
CREATE_ALWAYS = 2
FILE_FLAG_DELETE_ON_CLOSE = 0x04000000
INVALID_HANDLE_VALUE = ctypes.wintypes.HANDLE(-1)
ERROR_SHARING_VIOLATION = 32


CreateFile = ctypes.windll.kernel32.CreateFileW
CreateFile.argtypes = [
    ctypes.wintypes.LPWSTR,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.LPVOID,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HANDLE
]
CreateFile.restype = ctypes.wintypes.HANDLE

GetLastError = ctypes.windll.kernel32.GetLastError
GetLastError.restype = ctypes.wintypes.DWORD

CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
CloseHandle.restype = ctypes.wintypes.BOOL


class LockAlreadyLocked(RuntimeError):
  """Exception used when a lock couldn't be acquired."""
  pass


class WindowsError(Exception):
  """Error code returned from a windows API call.

  Values are documented here:
  https://msdn.microsoft.com/en-us/library/windows/desktop/ms681381(v=vs.85).aspx
  """
  pass


@contextlib.contextmanager
def flock(lockfile, lockdir=None):
  """Keeps a critical section from executing concurrently using a file lock.

  Example usage:

  try:
    with daemon.flock('toaster'):
      put_bread_in_toaster()
  except daemon.LockAlreadyLocked:
    print 'toaster is occupied!'
  """

  lockdir = lockdir or tempfile.gettempdir()
  full_lockfile = os.path.join(lockdir, lockfile)

  handle = ctypes.wintypes.HANDLE(CreateFile(
      full_lockfile,
      GENERIC_WRITE,
      0,  # shareMode - this is the important argument for exclusive locking.
      None,
      CREATE_ALWAYS,
      FILE_FLAG_DELETE_ON_CLOSE,
      0))

  if handle.value == INVALID_HANDLE_VALUE.value:
    errno = GetLastError()
    if errno == ERROR_SHARING_VIOLATION:
      raise LockAlreadyLocked()
    raise WindowsError(errno)

  try:
    yield
  finally:
    CloseHandle(handle)


def add_timeout(_cmd, _timeout_secs):  # pragma: no cover
  raise NotImplementedError


def become_daemon(_keep_fds=None):  # pragma: no cover
  raise NotImplementedError
