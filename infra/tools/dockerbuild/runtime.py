# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import contextlib
import logging
import multiprocessing
import os
import subprocess
import tempfile

from distutils.spawn import find_executable

from . import cipd
from . import dockcross
from . import platform
from . import source
from . import util


class MissingToolsError(RuntimeError):
  """Raised if required system tools could not be identified."""
  pass


class System(object):
  """Represents the local system facillities."""

  _Tools = collections.namedtuple('_Tools', (
      'gcloud', 'cipd'))

  _Dirs = collections.namedtuple('_Dirs', (
      'root', 'repo', 'bin', 'wheel', 'pkg', 'cipd_cache'))

  class SubcommandError(Exception):
    def __init__(self, returncode, output):
      super(System.SubcommandError, self).__init__(
          'subcommand returned %d' % (returncode,))
      self.returncode = returncode
      self.output = output

  def __init__(self, tools, dirs, leak, upload_sources, force_source_download):
    self._tools = tools
    self._dirs = dirs
    self._repo = source.Repository(self, dirs.repo, upload=upload_sources,
                                   force_download=force_source_download)
    self._leak = leak
    self._cipd = cipd.Cipd(self, dirs.cipd_cache)

    self._dockcross_images = {}

  @classmethod
  def initialize(cls, root, leak=False, upload_sources=False,
                 force_source_download=False):
    tools = cls._Tools(
        gcloud=cls._find_tool('gcloud'),
        cipd=cls._find_tool('cipd'),
    )
    missing_tools = [k for k, v in tools._asdict().iteritems() if not v]
    if missing_tools:
      raise MissingToolsError('Missing required tools: %r' % (
          sorted(missing_tools),))

    dirs = cls._Dirs(
        root=root,
        repo=util.ensure_directory(root, 'source_repo'),
        bin=util.ensure_directory(root, 'bin'),
        wheel=util.ensure_directory(root, 'wheels'),
        pkg=util.ensure_directory(root, 'packages'),
        cipd_cache=util.ensure_directory(root, 'cipd_cache'),
    )
    return cls(tools, dirs, leak, upload_sources, force_source_download)

  @classmethod
  def _find_tool(cls, name):
    return find_executable(name)

  @property
  def tools(self):
    return self._tools

  @property
  def root(self):
    return self._dirs.root

  @property
  def cipd(self):
    return self._cipd

  @property
  def bin_dir(self):
    return self._dirs.bin

  @property
  def wheel_dir(self):
    return self._dirs.wheel

  @property
  def pkg_dir(self):
    return self._dirs.pkg

  @property
  def repo(self):
    return self._repo

  @property
  def numcpu(self):
    return multiprocessing.cpu_count()

  def dockcross_image(self, plat, rebuild=False):
    if not rebuild:
      dx = self._dockcross_images.get(plat.name)
      if dx is not None:
        return dx

    if plat.dockcross_base:
      builder = dockcross.Builder(self)
      dx = builder.build(plat, rebuild=rebuild)
    else:
      # No "dockcross" image associated with this platform. We can return a
      # native image if the target platform is the current platform.
      native_platform = platform.NativePlatform()
      if plat == native_platform:
        util.LOGGER.info('Using native platform for [%s].', plat.name)
        dx = dockcross.NativeImage(self, plat)

    self._dockcross_images[plat.name] = dx
    return dx

  @contextlib.contextmanager
  def temp_subdir(self, prefix):
    temp_root = util.ensure_directory(self.root, 'temp')
    tdir = tempfile.mkdtemp(dir=temp_root, prefix=prefix)
    try:
      yield tdir
    finally:
      if self._leak:
        util.LOGGER.info('(--leak): Leaking temporary subdirectory: %s', tdir)
      else:
        util.LOGGER.debug('Removing temporary subdirectory: %s', tdir)
        util.removeall(tdir)

  def run(self, args, cwd=None, env=None, stdout=None, stderr=None,
          retcodes=None):
    # Fold enviornment augmentations into the default system environment.
    cwd = cwd or os.getcwd()
    util.LOGGER.debug('Running command: %s (env=%s; cwd=%s)', args, env, cwd)

    kwargs = {
        'cwd': cwd,
        'env': os.environ.copy(),
        'stdout': stdout or subprocess.PIPE,
        'stderr': stderr or subprocess.STDOUT,
    }
    if env is not None:
      kwargs['env'].update(env)

    stdout_lines = []
    with open(os.devnull, 'w') as fd:
      kwargs['stdin'] = fd
      proc = subprocess.Popen(args, **kwargs)

      if kwargs['stdout'] is subprocess.PIPE:
        for stdout_line in iter(proc.stdout.readline, ""):
          stdout_line = stdout_line.rstrip()
          util.LOGGER.debug('STDOUT: "%s"', stdout_line)
          stdout_lines.append(stdout_line)

      returncode = proc.wait()

    stdout = '\n'.join(stdout_lines)

    util.LOGGER.debug('Command finished with return code %d.', returncode)
    if retcodes is not None and proc.returncode not in retcodes:
      if not util.LOGGER.isEnabledFor(logging.DEBUG):
        util.LOGGER.error('Command failed (rc=%d):\n%s', returncode, stdout)
      else:
        # Already dumped STDOUT to debug.
        util.LOGGER.error('Command failed (rc=%d)', returncode)
      raise self.SubcommandError(returncode, stdout)
    return returncode, stdout

  def check_run(self, args, **kwargs):
    kwargs.setdefault('retcodes', [0])
    return self.run(args, **kwargs)

  def docker(self, args, **kwargs):
    cmd = [self.tools.gcloud, 'docker', '--']
    cmd += args
    return self.run(cmd, **kwargs)
