# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# pylint: disable=E0711, W0613, R0201
class Repository(object):  # pragma: no cover
  """An interface for source code repository."""

  def GetChangeLog(self, revision):
    """Returns the change log of the given revision."""
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
