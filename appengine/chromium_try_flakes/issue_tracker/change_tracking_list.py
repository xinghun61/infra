# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A wrapper around list that keep track of changes to it."""


class ChangeTrackingList(list):  # pragma: no cover
  def __init__(self, seq=()):
    list.__init__(self, seq)
    self.added = set()
    self.removed = set()

  def append(self, p_object):
    list.append(self, p_object)
    if p_object in self.removed:
      self.removed.remove(p_object)
    else:
      self.added.add(p_object)

  def remove(self, value):
    list.remove(self, value)

    if value in self.added:
      self.added.remove(value)
    else:
      self.removed.add(value)

  def isChanged(self):
    return (len(self.added) + len(self.removed)) > 0

  def reset(self):
    self.added.clear()
    self.removed.clear()
