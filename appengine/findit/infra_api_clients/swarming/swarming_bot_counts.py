# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class SwarmingBotCounts(object):
  """Represents counts of swarming bots in different states."""

  def __init__(self, counts):
    """
    Args:
      counts (dict): A dict of integers for bot counts in different states.
    """
    self.count = int(counts.get('count', 0))
    self.busy = int(counts.get('busy', 0))
    self.dead = int(counts.get('dead', 0))
    self.quarantined = int(counts.get('quarantined', 0))

  @property
  def available(self):
    return self.count - self.busy - self.dead - self.quarantined

  def Serialize(self):
    return {
        'count': self.count,
        'available': self.available,
        'busy': self.busy,
        'dead': self.dead,
        'quarantined': self.quarantined,
    }
