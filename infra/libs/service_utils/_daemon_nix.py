# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import errno
import fcntl
import os
import sys
import tempfile


@contextlib.contextmanager
def _auto_closing_fd(*args, **kwargs):
  """Opens a file, yields its fd, and closes it when done."""

  fd = os.open(*args, **kwargs)
  yield fd
  os.close(fd)


class LockAlreadyLocked(RuntimeError):
  """Exception used when a lock couldn't be acquired."""
  pass


@contextlib.contextmanager
def flock(lockfile, lockdir=None):
  """Keeps a critical section from executing concurrently using a file lock.

  This only protects critical sections across processes, not threads. For
  multithreaded programs. use threading.Lock or threading.RLock.

  Implementation based on http://goo.gl/dNf7fv (see John Mudd's comment) and
  http://stackoverflow.com/a/18745264/3984761. This implementation creates the
  lockfile if it doesn't exist and removes it when the critical section exits.
  It raises LockAlreadyLocked if it cannot acquire a lock.

  Note 1: this method only works for lockfiles on local filesystems with
  appropriate locking semantics (extfs, HFS+). It is unwise to use this on
  NFS-mounted filesystems.

  Note 2: be careful when forking processes within the lock, forked processes
  inherit open file descriptors.

  Example usage:

  try:
    with daemon.flock('toaster'):
      put_bread_in_toaster()
  except daemon.LockAlreadyLocked:
    print 'toaster is occupied!'
  """

  lockdir = lockdir or tempfile.gettempdir()
  full_lockfile = os.path.join(lockdir, lockfile)

  with _auto_closing_fd(
      full_lockfile, os.O_CREAT | os.O_TRUNC | os.O_WRONLY) as fd:
    try:
      # Request exclusive (EX) non-blocking (NB) advisory lock.
      fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    except IOError:
      # Could not obtain lock.
      raise LockAlreadyLocked()

    try:
      held_inode = os.fstat(fd).st_ino
      file_inode = os.stat(full_lockfile).st_ino

      if held_inode != file_inode:
        # The file was deleted under us, another process has created it again
        # and may get a lock on it. That process doesn't know about the lock
        # we have on the (now deleted) file, so we need to bail.
        raise LockAlreadyLocked()
    except OSError:
     # File has been deleted under us. We have to exit because another process
     # might try to create it and obtain a lock, not knowing that we had a
     # lock on the (now deleted) file.
     raise LockAlreadyLocked()

    yield

    try:
      # The order of these two operations is very important. We need to delete
      # the file before we release the lock. If we release the lock before we
      # delete the file, we run the risk of another process obtaining a lock on
      # the file we're about to delete. If the delete happens while the other
      # critical section is running, a third process could create the file, get
      # a lock on it, and run a second critical section simultaneously. Deleting
      # before unlocking prevents this scenario.
      os.unlink(full_lockfile)
      fcntl.lockf(fd, fcntl.LOCK_UN)
    except OSError:
      # If the file was deleted for some other reason, don't sweat it.
      pass


def _fork_then_exit_parent():
  pid = os.fork()
  if pid > 0:
    os._exit(0)


def become_daemon(keep_fds=None):
  """Makes this process a daemon process.

  Starts a new process group, closes all open file handles, opens /dev/null on
  stdin, stdout and stderr, and changes the current working directory to /.
  """

  if keep_fds is None:
    keep_fds = set()

  _fork_then_exit_parent()
  os.setsid()
  _fork_then_exit_parent()

  # Close all open files.
  for fd in reversed(range(2048)):
    if fd in keep_fds:
      continue

    try:
      os.close(fd)
    except EnvironmentError as ex:
      if ex.errno != errno.EBADF:
        raise

  # Open /dev/null on stdin, stdout and stderr.
  null = os.open(os.devnull, os.O_RDWR)
  for i in range(3):
    os.dup2(null, i)

  os.chdir('/')
