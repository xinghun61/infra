# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import errno
import fnmatch
import logging
import os
import subprocess
import sys
import tempfile
import time
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

  def __hash__(self):
    return hash((self._url, self._repo_path))

  def __getitem__(self, ref):
    """Get a Ref attached to this Repo."""
    return Ref(self, ref)

  # Accessors
  # pylint: disable=W0212
  url = property(lambda self: self._url)
  repo_path = property(lambda self: self._repo_path)

  def reify(self, share_from=None):
    """Ensures the local mirror of this Repo exists.

    Args:
      share_from - Either a Repo, or a path to a git repo (on disk). This will
                   cause objects/info/alternates to be set up to point to the
                   other repo for objects.
    """
    assert self.repos_dir is not None

    if not os.path.exists(self.repos_dir):
      try:
        self._log.info('making repos dir: %s', self.repos_dir)
        os.makedirs(self.repos_dir)
      except OSError as e:  # pragma: no cover
        if e.errno != errno.EEXIST:
          raise

    parsed = urlparse.urlparse(self.url)
    norm_url = parsed.netloc + parsed.path
    if norm_url.endswith('.git'):
      norm_url = norm_url[:-len('.git')]
    folder = norm_url.replace('-', '--').replace('/', '-').lower()

    rpath = os.path.abspath(os.path.join(self.repos_dir, folder))

    share_objects = None
    if share_from:
      if isinstance(share_from, Repo):
        assert share_from.repo_path, 'share_from target must be reify()\'d'
        share_from = share_from.repo_path
      share_objects = os.path.join(share_from, 'objects')

    if not os.path.isdir(rpath):
      self._log.debug('initializing %r -> %r', self, rpath)
      tmp_path = tempfile.mkdtemp(dir=self.repos_dir)
      args = ['clone', '--mirror', self.url, os.path.basename(tmp_path)]
      if share_objects:
        args.extend(('--reference', os.path.dirname(share_objects)))
      self.run(*args, stdout=sys.stdout, stderr=sys.stderr, cwd=self.repos_dir)
      os.rename(os.path.join(self.repos_dir, tmp_path),
                os.path.join(self.repos_dir, folder))
    else:
      if share_objects:
        altfile = os.path.join(rpath, 'objects', 'info', 'alternates')
        try:
          os.makedirs(os.path.dirname(altfile))
        except OSError as e:
          if e.errno != errno.EEXIST:
            raise  # pragma: no cover

        add_entry = not os.path.exists(altfile)
        if not add_entry:
          with open(altfile, 'r') as f:
            add_entry = share_objects in f.readlines()
        if add_entry:
          with open(altfile, 'a') as f:
            print >> f, share_objects
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
        yield self[ref]

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

    if 'cwd' not in kwargs:
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
    started = time.time()
    process = subprocess.Popen(cmd, **kwargs)
    output, errout = process.communicate(indata)
    retcode = process.poll()
    dt = time.time() - started
    if dt > 1:  # pragma: no cover
      self._log.debug('Finished in %.1f sec', dt)
    if retcode not in ok_ret:
      raise CalledProcessError(retcode, cmd, output, errout)

    if errout:
      sys.stderr.write(errout)
    return output

  def intern(self, data, typ='blob'):
    return self.run(
        'hash-object', '-w', '-t', typ, '--stdin', indata=str(data)).strip()

  def fast_forward_push(self, refs_and_commits):
    """Push commits to refs on the remote, and also update refs' local copies.

    Refs names are specified as refs on remote, i.e. push to
    Ref('refs/heads/master') would update 'refs/heads/master' on remote (and on
    local repo mirror), no ref name translation is happening.

    Args:
      refs_and_commits: dict {Ref object -> Commit to push to the ref}.
    """
    if not refs_and_commits:
      return
    refspec = [
      '%s:%s' % (c.hsh, r.ref)
      for r, c in refs_and_commits.iteritems()
    ]
    self.run('push', 'origin', *refspec)
    for r, c in refs_and_commits.iteritems():
      r.update_to(c)
