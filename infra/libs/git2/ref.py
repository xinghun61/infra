# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra.libs.git2.util import CalledProcessError
from infra.libs.git2.util import INVALID

class Ref(object):
  """Represents a single ref in a git Repo.

  Allowed to hold anything which can resolve to a single commit e.g.:

  >>> r = Repo()
  >>> r['refs/heads/master'].commit
  # Commit which is the current value of master
  >>> r['refs/heads/master~1'].commit
  # Commit which is the current first parent of master
  >>> r[raw_git_hash].to(r[other_git_hash])
  # generator of all Commits from raw_git_hash to other_git_hash

  May also hold INVALID or point to a ref which does not exist yet.

  >>> r = Repo()
  >>> r[some.expression.which.returns.INVALID].to(other_ref)
  # generator of all commits reachable from other_ref
  >>> r[INVALID].update_to(Commit())
  # => AssertionError
  >>> r['/ref/which/does_not/exist_yet'].to(other_ref)
  # generator of all commits reachable from other_ref
  >>> r['/ref/which/does_not/exist_yet'].update_to(Commit())
  # works
  """
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

  def __hash__(self):
    return hash((self._repo, self._ref))

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
    if self._ref is INVALID:
      return INVALID
    try:
      return self._repo.get_commit(
        self._repo.run('rev-parse', self._ref).strip())
    except CalledProcessError:
      return INVALID

  # Methods
  def to(self, other, path=None, first_parent=False):
    """Generate Commit()'s which occur from `self..other`.

    If the current ref is INVAILD, list all of the commits reachable from
    other.

    Args:
      first_parent - only return commits following the first parent of
         merge commits.
      path - A string indicating a repo-root-relative path to filter commits on.
             Only Commits which change this path will be yielded. See help for
             `git rev-list self..other -- <path>`.
    """
    args = ['rev-list', '--reverse']
    if first_parent:
      args.append('--first-parent')
    if self.commit is INVALID:
      args.append(other.ref)
    else:
      args.append('%s..%s' % (self.ref, other.ref))
    if path:
      args.extend(['--', path])
    for hsh in self.repo.run(*args).splitlines():
      yield self.repo.get_commit(hsh)

  def update_to(self, commit):
    """Update the local copy of the ref to ``commit``."""
    assert self._ref is not INVALID, 'May not update Ref(INVALID)'
    self.repo.run('update-ref', self.ref, commit.hsh)

  def fast_forward(self, commit):
    """Fast forward the local copy of the ref to ``commit``.

    Allows fast forward from undefined to a value as well.
    """
    if self.commit is not INVALID:
      self.repo.run('merge-base', '--is-ancestor', self.commit.hsh, commit.hsh)
    self.update_to(commit)
