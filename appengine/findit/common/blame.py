# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Region(object):
  """Represents a region in a file blame."""
  def __init__(self, start, count, revision,
               author_name, author_email, author_time):
    self.start = start
    self.count = count
    self.revision = revision
    self.author_name = author_name
    self.author_email = author_email
    self.author_time = author_time

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
  """Represents a file blame."""
  def __init__(self, revision, path):
    super(Blame, self).__init__()
    self.revision = revision
    self.path = path

  def AddRegion(self, region):
    self.append(region)

  def ToDict(self):
    regions = []
    for region in self:
      regions.append(region.ToDict())
    return {
        'revision': self.revision,
        'path': self.path,
        'regions': regions
    }
