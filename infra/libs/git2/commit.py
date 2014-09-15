# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from infra.libs.decorators import cached_property

from infra.libs.git2.util import CalledProcessError
from infra.libs.git2.util import INVALID
from infra.libs.git2.data import CommitData


LOGGER = logging.getLogger(__name__)


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

    If self has more than one parent, returns INVALID.
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
