# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import os
import platform
import re
import tempfile
import shutil
import subprocess
import sys


# Copied from pip.wheel.Wheel.wheel_file_re to avoid requiring pip here.
WHEEL_FILE_RE = re.compile(
  r"""^(?P<namever>(?P<name>.+?)-(?P<ver>\d.*?))
  ((-(?P<build>\d.*?))?-(?P<pyver>.+?)-(?P<abi>.+?)-(?P<plat>.+?)
  \.whl)$""",
  re.VERBOSE
)


class GlycoError(Exception):
  """Base class for Glyco errors"""


class GlycoSetupError(GlycoError):
  """Issue outside the reach of Glyco that prevents execution."""


class InvalidWheelFile(GlycoError):
  """The file passed is not a valid wheel file.

  This includes errors on the file name.
  """


def setup_virtualenv(env_path, relocatable=False):
  """Create a virtualenv in specified location.

  The virtualenv contains a standard Python installation, plus setuptools, pip
  and wheel.

  Args:
    env_path (str): where to create the virtual environment.

  """
  if os.path.exists(os.path.join(os.path.expanduser('~'), '.pydistutils.cfg')):
    raise GlycoSetupError('\n'.join([
      '',
      'You have a ~/.pydistutils.cfg file, which interferes with the ',
      'infra virtualenv environment. Please move it to the side and bootstrap ',
      'again. Once infra has bootstrapped, you may move it back.',
      '',
      'Upstream bug: https://github.com/pypa/virtualenv/issues/88/',
      ''
    ]))

  print 'Creating environment: %r' % env_path

  if os.path.exists(env_path):
    print '  Removing existing one...'
    shutil.rmtree(env_path, ignore_errors=True)

  print '  Building new environment...'
  # Import bundled virtualenv lib
  import virtualenv  # pylint: disable=F0401
  virtualenv.create_environment(
    env_path, search_dirs=virtualenv.file_search_dirs())

  if relocatable:
    print '  Make environment relocatable'
    virtualenv.make_environment_relocatable(env_path)

  print 'Done creating environment'


def platform_tag():
  if sys.platform.startswith('linux'):
    return '_{0}_{1}'.format(*platform.linux_distribution())
  return ''


class Virtualenv(object):
  def __init__(self, prefix='glyco-', keep_directory=False):
    """Helper class to run commands from virtual environments.

    Keyword Args:
      prefix (str): prefix to the temporary directory used to create the
        virtualenv.
      keep_directory (boolean): if True the temporary virtualenv directory is
        kept around instead of being deleted. Useful mainly for debugging.

    Returns: self. Only the check_call and check_output methods are meant to be
      used inside the with block.
    """
    self._prefix = prefix
    self._keep_directory = keep_directory

    # Where the virtualenv is
    self._venvdir = None
    self._bin_dir = 'Scripts' if sys.platform.startswith('win') else 'bin'

  def check_call(self, args, **kwargs):
    """Run a command from inside the virtualenv using check_call.

    Args:
      cmd (str): name of the command. Must be found in the 'bin' directory of
        the virtualenv.
      args (list of strings): arguments passed to the command.
    Keyword Args:
      kwargs: keyword arguments passed to subprocess.check_output
    """
    subprocess.check_call(
      (os.path.join(self._venvdir, self._bin_dir, args[0]),) + tuple(args[1:]),
      **kwargs)

  def check_output(self, args, **kwargs):
    """Run a command from inside the virtualenv using check_output.

    Args:
      cmd (str): name of the command. Must be found in the 'bin' directory of
        the virtualenv.
      args (list of strings): arguments passed to the command.
    Keyword Args:
      kwargs: keyword arguments passed to subprocess.check_output
    """
    return subprocess.check_output(
      (os.path.join(self._venvdir, self._bin_dir, args[0]),) + tuple(args[1:]),
      **kwargs)

  def __cleanup_venv(self):
    """Remove the virtualenv directory"""
    try:
      # TODO(pgervais,496347) Make this work reliably on Windows.
      shutil.rmtree(self._venvdir, ignore_errors=True)
    except OSError as ex:
      print >> sys.stderr, (
        "ERROR: {!r} while cleaning up {!r}".format(ex, self._venvdir))
    self._venvdir = None


  def __enter__(self):
    self._venvdir = tempfile.mkdtemp('', self._prefix, None)
    try:
      setup_virtualenv(self._venvdir)
    except Exception:
      self.__cleanup_venv()
      raise
    return self

  def __exit__(self, err_type, value, tb):
    if self._venvdir and not self._keep_directory:
      self.__cleanup_venv()


# dir is a built-in. We're matching the Python 3 function signature here.
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
