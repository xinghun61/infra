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

from infra.services.gnumbd.support.util import (
    cached_property, CalledProcessError)

from infra.services.gnumbd.support.data import CommitData

LOGGER = logging.getLogger(__name__)


class _Invalid(object):
  def __call__(self, *_args, **_kwargs):
    return self

  def __getattr__(self, _key):
    return self

  def __eq__(self, _other):
    return False

  def __ne__(self, _other):  # pylint: disable=R0201
    return True

INVALID = _Invalid()


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


class Commit(object):
  """Represents the identity of a commit in a git repo."""

  def __init__(self, repo, hsh):
    """
    @type repo: Repo
    """
    assert CommitData.HASH_RE.match(hsh)
    self._repo = repo
    self._hsh = hsh

  # Comparison & Representation
  def __eq__(self, other):
    return (self is other) or (
        isinstance(other, Commit) and (
            self.hsh == other.hsh
        )
    )

  def __ne__(self, other):
    return not (self == other)

  def __repr__(self):
    return 'Commit({_repo!r}, {_hsh!r})'.format(**self.__dict__)

  # Accessors
  # pylint: disable=W0212
  repo = property(lambda self: self._repo)
  hsh = property(lambda self: self._hsh)

  # Properties
  @cached_property
  def data(self):
    """Get a structured data representation of this commit."""
    try:
      raw_data = self.repo.run('cat-file', 'commit', self.hsh)
    except CalledProcessError:
      return INVALID
    return CommitData.from_raw(raw_data)

  @cached_property
  def parent(self):
    """Get the corresponding parent Commit() for this Commit(), or None.

    If self has more than one parent, this raises an Exception.
    """
    parents = self.data.parents
    if len(parents) > 1:
      LOGGER.error('Commit %r has more than one parent!', self.hsh)
      return INVALID
    return self.repo.get_commit(parents[0]) if parents else None

  # Methods
  def alter(self, **kwargs):
    """Get a new Commit which is the same as this one, except for alterations
    specified by kwargs.

    This will intern the new Commit object into the Repo.
    """
    return self.repo.get_commit(
        self.repo.intern(self.data.alter(**kwargs), 'commit'))


class Ref(object):
  """Represents a single simple ref in a git Repo."""
  def __init__(self, repo, ref_str):
    """
    @type repo: Repo
    @type ref_str: str
    """
    self._repo = repo
    self._ref = ref_str

  # Comparison & Representation
  def __eq__(self, other):
    return (self is other) or (
        isinstance(other, Ref) and (
            self.ref == other.ref and
            self.repo is other.repo
        )
    )

  def __ne__(self, other):
    return not (self == other)

  def __repr__(self):
    return 'Ref({_repo!r}, {_ref!r})'.format(**self.__dict__)

  # Accessors
  # pylint: disable=W0212
  repo = property(lambda self: self._repo)
  ref = property(lambda self: self._ref)

  # Properties
  @property
  def commit(self):
    """Get the Commit at the tip of this Ref."""
    try:
      val = self._repo.run('show-ref', '--verify', self._ref)
    except CalledProcessError:
      return INVALID
    return self._repo.get_commit(val.split()[0])

  # Methods
  def to(self, other):
    """Generate Commit()'s which occur from `self..other`."""
    assert self.commit is not INVALID
    arg = '%s..%s' % (self.ref, other.ref)
    for hsh in self.repo.run('rev-list', '--reverse', arg).splitlines():
      yield self.repo.get_commit(hsh)

  def fast_forward_push(self, commit):
    """Push |commit| to this ref on the remote, and update the local copy of the
    ref to |commit|."""
    self.repo.run('push', 'origin', '%s:%s' % (commit.hsh, self.ref))
    self.update_to(commit)

  def update_to(self, commit):
    """Update the local copy of the ref to |commit|."""
    self.repo.run('update-ref', self.ref, commit.hsh)
