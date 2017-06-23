# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple


class Region(
    namedtuple('Region', [
        'start', 'count', 'revision', 'author_name', 'author_email',
        'author_time'
    ])):
  """A region of some (unspecified) file at a (known) revision."""
  __slots__ = ()

  def ToDict(self):
    return {
        'start': self.start,
        'count': self.count,
        'revision': self.revision,
        'author_name': self.author_name,
        'author_email': self.author_email,
        'author_time': self.author_time
    }


class Blame(list):
  """A list of regions for a (known) revision of a (known) file."""

  def __init__(self, revision, path):
    super(Blame, self).__init__()
    self.revision = revision
    self.path = path

  def AddRegion(self, region):
    """Add a single region to this object.

    Args:
      region (Region): the region to add
    """
    self.append(region)

  def AddRegions(self, regions):
    """Add multiple regions to this object.

    Args:
      regions (iterable of Region): the regions to add.
    """
    self.extend(regions)

  def ToDict(self):
    regions = []
    for region in self:
      regions.append(region.ToDict())
    return {'revision': self.revision, 'path': self.path, 'regions': regions}
