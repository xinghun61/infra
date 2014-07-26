# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import fnmatch
import logging
import os
import subprocess
import sys
import tempfile
import urlparse

from infra.libs.git2 import CalledProcessError
from infra.libs.git2 import Commit
from infra.libs.git2 import Ref

LOGGER = logging.getLogger(__name__)


class Repo(object):
  """Represents a remote git repo.

  Manages the (bare) on-disk mirror of the remote repo.
  """
  MAX_CACHE_SIZE = 1024

  def __init__(self, url):
    self.dry_run = False
    self.repos_dir = None

    self._url = url
    self._repo_path = None
    self._commit_cache = collections.OrderedDict()
    self._log = LOGGER.getChild('Repo')

  def __getitem__(self, ref):
    """Get a Ref attached to this Repo."""
    return Ref(self, ref)

  def reify(self):
    """Ensures the local mirror of this Repo exists."""
    assert self.repos_dir is not None
    parsed = urlparse.urlparse(self._url)
    norm_url = parsed.netloc + parsed.path
    if norm_url.endswith('.git'):
      norm_url = norm_url[:-len('.git')]
    folder = norm_url.replace('-', '--').replace('/', '-').lower()

    rpath = os.path.abspath(os.path.join(self.repos_dir, folder))
    if not os.path.isdir(rpath):
      self._log.debug('initializing %r -> %r', self, rpath)
      name = tempfile.mkdtemp(dir=self.repos_dir)
      self.run('clone', '--mirror', self._url, os.path.basename(name),
               stdout=sys.stdout, stderr=sys.stderr, cwd=self.repos_dir)
      os.rename(os.path.join(self.repos_dir, name),
                os.path.join(self.repos_dir, folder))
    else:
      self._log.debug('%r already initialized', self)
    self._repo_path = rpath

    # This causes pushes to fail, so unset it.
    self.run('config', '--unset', 'remote.origin.mirror', ok_ret={0, 5})

  # Representation
  def __repr__(self):
    return 'Repo({_url!r})'.format(**self.__dict__)

  # Methods
  def get_commit(self, hsh):
    """Creates a new |Commit| object for this |Repo|.

    Uses a very basic LRU cache for commit objects, keeping up to
    |MAX_CACHE_SIZE| before eviction. This cuts down on the number of redundant
    git commands by > 50%, and allows expensive cached_property's to remain
    for the life of the process.
    """
    if hsh in self._commit_cache:
      self._log.debug('Hit %s', hsh)
      r = self._commit_cache.pop(hsh)
    else:
      self._log.debug('Miss %s', hsh)
      if len(self._commit_cache) >= self.MAX_CACHE_SIZE:
        self._commit_cache.popitem(last=False)
      r = Commit(self, hsh)

    self._commit_cache[hsh] = r
    return r

  def refglob(self, globstring):
    """Yield every Ref in this repo which matches |globstring|."""
    for _, ref in (l.split() for l in self.run('show-ref').splitlines()):
      if fnmatch.fnmatch(ref, globstring):
        yield Ref(self, ref)

  def run(self, *args, **kwargs):
    """Yet-another-git-subprocess-wrapper.

    Args: argv tokens. 'git' is always argv[0]

    Kwargs:
      indata - String data to feed to communicate()
      ok_ret - A set() of valid return codes. Defaults to {0}.
      ...    - passes through to subprocess.Popen()
    """
    if args[0] == 'push' and self.dry_run:
      self._log.warn('DRY-RUN: Would have pushed %r', args[1:])
      return

    if not 'cwd' in kwargs:
      assert self._repo_path is not None
      kwargs.setdefault('cwd', self._repo_path)

    kwargs.setdefault('stderr', subprocess.PIPE)
    kwargs.setdefault('stdout', subprocess.PIPE)
    indata = kwargs.pop('indata', None)
    if indata:
      assert 'stdin' not in kwargs
      kwargs['stdin'] = subprocess.PIPE
    ok_ret = kwargs.pop('ok_ret', {0})
    cmd = ('git',) + args

    self._log.debug('Running %r', cmd)
    process = subprocess.Popen(cmd, **kwargs)
    output, errout = process.communicate(indata)
    retcode = process.poll()
    if retcode not in ok_ret:
      raise CalledProcessError(retcode, cmd, output, errout)

    if errout:
      sys.stderr.write(errout)
    return output

  def intern(self, data, typ='blob'):
    return self.run(
        'hash-object', '-w', '-t', typ, '--stdin', indata=str(data)).strip()
