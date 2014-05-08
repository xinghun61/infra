# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility for dealing with Git repositories."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile

from types import MethodType


LOGGER = logging.getLogger(__name__)


class GitException(UserWarning):
  pass


class Git(object):
  """Wrapper class to abstract git operations against a single repository."""

  def __init__(self, path):
    """Creates the Git object, pointed at the on-disk repo.

    Args:
      @param path: The absolute or relative path to the repository on disk.
      @type path: string
    Returns:
      @type string
    Raises:
      @type TypeError
      @type subprocess.CalledProcessError
    """
    self.path = os.path.abspath(path)

  def __call__(self, *args, **kwargs):
    """Run a git command and returns its combined stdout and stderr."""
    cmd = ['git'] + [str(arg) for arg in args]
    LOGGER.debug('Running %s', ' '.join(cmd))
    out = subprocess.check_output(
        cmd, stderr=subprocess.STDOUT, cwd=self.path, **kwargs)
    return out

  @property
  def bare(self):
    """True if the repository is bare (is just the .git directory)."""
    return self('config', '--get', 'core.bare').strip() == 'true'

  def show(self, ref, path, *args):
    """Get the contents of a Git object (blob, tree, tag, or commit).

    Args:
      @param ref: The ref at which to show the object. Can be ''.
      @type ref: string
      @param path: The path to the blob or tree, relative to repository root.
      @type path: string
    """
    treeish = ref + (':%s' % path if path else '')
    cmd = ['show', treeish] + list(args)
    return self(*cmd)

  def number(self, *refs):
    """Get the generation number of each input ref.

    Args:
      @param refs: tuple of refishes to number
      @type refs: tuple
    Returns:
      @type list of int
    """
    cmd = ['number'] + list(refs)
    out = self(*cmd)
    return map(int, out.splitlines())


def NewGit(url, path, bare=False):
  """Factory function to create a Git object against a remote url.

  Ensures the given path exists. If a git repository is already present
  ensures that it points at the given url; otherwise, creates a git repository
  from the given url. Returns a Git object pointing at the local directory.

  Args:
    @param url: The url of the remote repository.
    @type url: string
    @param path: The path to the local version of the repository.
    @type path: string
    @param bare: Whether or not the local repo should be a bare clone.
    @type bare: bool
  Returns:
    @type Git
  Raises:
    @type GitException
  """
  # If the directory doesn't exist, create it.
  if not os.path.isdir(path):
    os.makedirs(path)

  git = Git(path)

  # If the directory has nothing in it, clone into it.
  if not os.listdir(path):
    b = ['--bare'] if bare else []
    clone_cmd = ['clone'] + b + [url, '.']
    git(*clone_cmd)
    return git

  # If the directory is already correctly configured for this repo, fetch.
  try:
    if git('config', '--get', 'remote.origin.url').strip() != url:
      msg = ('A Git repo at %s exists, '
             'but has %s configured as remote origin url.' % (path, url))
      LOGGER.error(msg)
      raise GitException(msg)
    if git.bare != bare:
      msg = ('A Git repo at %s exists, but is %sbare.' %
             (path, 'not ' if not git.bare else ''))
      LOGGER.error(msg)
      raise GitException(msg)
  except subprocess.CalledProcessError:
    msg = 'There appears to already be something else at %s.' % path
    LOGGER.error(msg)
    raise GitException(msg)

  try:
    git('fetch', 'origin')
  except subprocess.CalledProcessError:
    LOGGER.error('Failed to fetch origin.')
  return git


def TmpGit(url, bare=False):
  """Factory function to create a temporary Git object against a remote url.

  Creates a temporary directory, clones the repository into that directory,
  and returns a Git object pointing at that temporary directory. The instance
  will clean up after itself by deleting the temporary directory.

  Args:
    @param url: The url of the remote repository.
    @type url: string
    @param bare: Whether or not the local repo should be a bare clone.
    @type bare: bool
  Returns:
    @type Git
  """
  path = tempfile.mkdtemp()
  git = NewGit(url, path, bare)

  def __del__(git_obj):
    """Destroy the temporary directory."""
    def rm_on_error(func, path, exc):
      """Error handling function to enforce removal of readonly files."""
      if sys.platform.startswith('win'):
        # On windows, we'll just fall back to using cmd.exe's rd.
        import time
        for _ in xrange(3):
          exitcode = subprocess.call(['cmd.exe', '/c', 'rd', '/q', '/s', path])
          if exitcode == 0:
            return
          else:
            LOGGER.warn('rd exited with code %d', exitcode)
          time.sleep(3)
        LOGGER.fatal('Failed to remove path %s', path)
      else:
        import stat
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 777
        shutil.rmtree(path, ignore_errors=False, onerror=rm_on_error)

    shutil.rmtree(git_obj.path, ignore_errors=False, onerror=rm_on_error)

  git.__del__ = MethodType(__del__, git, Git)

  return git
