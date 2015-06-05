# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import os
import platform
import tempfile
import shutil
import subprocess
import sys


class GlycoSetupError(Exception):
  """Issue outside the reach of Glyco that prevents execution."""


def pip(*args, **kwargs):
  """Run pip from the current environment."""
  bin_dir = 'Scripts' if sys.platform.startswith('win') else 'bin'
  subprocess.check_call(
      (os.path.join(sys.prefix, bin_dir, 'pip'),) + args, **kwargs)


def platform_tag():
  if sys.platform.startswith('linux'):
    return '_{0}_{1}'.format(*platform.linux_distribution())
  return ''


# pylint: disable=redefined-builtin
@contextlib.contextmanager
def temporary_directory(suffix="", prefix="tmp", dir=None,
                        keep_directory=False):
  """Create and return a temporary directory.  This has the same
  behavior as mkdtemp but can be used as a context manager.  For
  example:

    with temporary_directory() as tmpdir:
      ...

  Upon exiting the context, the directory and everything contained
  in it are removed.

  Args:
    suffix, prefix, dir: same arguments as for tempfile.mkdtemp.
    keep_directory (bool): if True, do not delete the temporary directory
      when exiting. Useful for debugging.

  Returns:
    tempdir (str): full path to the temporary directory.
  """
  tempdir = None  # Handle mkdtemp raising an exception
  try:
    tempdir = tempfile.mkdtemp(suffix, prefix, dir)
    yield tempdir

  finally:
    if tempdir and not keep_directory:
      try:
        # TODO(pgervais,496347) Make this work reliably on Windows.
        shutil.rmtree(tempdir, ignore_errors=True)
      except OSError as ex:
        print >> sys.stderr, (
          "ERROR: {!r} while cleaning up {!r}".format(ex, tempdir))
