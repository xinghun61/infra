# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module defines an interface of a meta structure -- ``MetaObject``.

We can consider ``MetaObject`` as inner node, and it has ``is_meta`` property.
``MetaObject`` is good way to group leaf nodes (which have some real value).

An easy example for ``MetaDict``:
MetaDict({'a': 1, 'b': MetaDict({'c': 2, 'd': 3})}), its leaves are
{'a': 1, 'c': 2, 'd': 3}.

An use case in Predator is that being a subclass of ``MetaDict``,
``MetaFeature``  can group relevant features together to share common
operations.
"""

class MetaObject(object):
  """Class that can be either one element or a collection of elements."""

  @property
  def is_meta(self):  # pragma: no cover
    return True


class MetaDict(dict, MetaObject):
  """Dict-like object containing a collection of ``MetaObject``s."""

  @property
  def leaves(self):
    """Gets a dict of all leaf items."""
    leaves = {}
    for key, value in self.iteritems():
      if not hasattr(value, 'is_meta'):
        leaves[key] = value
      else:
        leaves.update(value.leaves)

    return leaves

  def iterleaves(self):
    """Iterates leaf items."""
    for key, value in self.iteritems():
      if not hasattr(value, 'is_meta'):
        yield (key, value)
      else:
        for sub_key, sub_value in value.iterleaves():
          yield (sub_key, sub_value)

  def UpdateLeaves(self, leaves):
    """Update leaf nodes by a dict - ``leaves``."""
    for key, value in self.iteritems():
      if not hasattr(value, 'is_meta'):
        if key in leaves:
          self[key] = leaves[key]
      else:
        value.UpdateLeaves(leaves)

  def __eq__(self, other):
    for key, value in self.iteritems():
      if key not in other or value != other[key]:
        return False

    return True

  def __ne__(self, other):
    return not self.__eq__(other)
