# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from infra.libs.git2.util import CalledProcessError
from infra.libs.git2.util import INVALID

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
    try:
      val = self._repo.run('show-ref', '--verify', self._ref)
    except CalledProcessError:
      return INVALID
    return self._repo.get_commit(val.split()[0])

  # Methods
  def to(self, other, path=None):
    """Generate Commit()'s which occur from `self..other`.

    If the current ref is INVAILD, list all of the commits reachable from
    other.

    Args:
      path - A string indicating a repo-root-relative path to filter commits on.
             Only Commits which change this path will be yielded. See help for
             `git rev-list self..other -- <path>`.
    """
    args = ['rev-list', '--reverse']
    if self.commit is INVALID:
      args.append(other.ref)
    else:
      args.append('%s..%s' % (self.ref, other.ref))
    if path:
      args.extend(['--', path])
    for hsh in self.repo.run(*args).splitlines():
      yield self.repo.get_commit(hsh)

  def update_to(self, commit):
    """Update the local copy of the ref to |commit|."""
    self.repo.run('update-ref', self.ref, commit.hsh)

  def fast_forward(self, commit):
    """Fast forward the local copy of the ref to |commit|."""
    with open(os.devnull, 'w') as f:
      self.repo.run('push', '.', '%s:%s' % (commit.hsh, self.ref),
                    stderr=f)
