# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# pylint: disable=E0711, W0613, R0201
class GitRepository(object):  # pragma: no cover
  """An interface for access to a Git repository."""

  def GetChangeLog(self, revision):
    """Returns the change log of the given revision."""
    raise NotImplemented()

  def GetChangeLogs(self, start_revision, end_revision, **kwargs):
    """Returns change log list in (start_revision, end_revision].

    Args:
      start_revision: The oldest revision in the range. If it's None, we will
        return all commits before and including end_revision (since the very
        first commit).
      end_revision: The latest revision in the range. If it's None, we will
        return all commits after the start_revision (till the latest commit).
      kwargs(dict): Keyword arguments passed as additional params for the query.
    """
    raise NotImplemented()

  def GetChangeDiff(self, revision):
    """Returns the diff of the given revision."""
    raise NotImplemented()

  def GetBlame(self, path, revision):
    """Returns blame of the file at ``path`` of the given revision."""
    raise NotImplemented()

  def GetSource(self, path, revision):
    """Returns source code of the file at ``path`` of the given revision."""
    raise NotImplemented()

  def GetNChangeLogs(self, revision, n):
    """Returns the changelogs for revision and its n - 1 immediate ancestors."""
    raise NotImplemented()
