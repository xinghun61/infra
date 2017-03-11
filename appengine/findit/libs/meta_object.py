# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module defines an interface of a meta structure -- ``MetaObject``.

We can consider ``MetaObject`` as tree node, and it has ``is_element`` property
for us to tell whether it is a leaf or not. We can think ``MetaObject`` is an
effective way to group elements, basically each ``MetaObject``(tree root)
controls all the ``Element``s (leaf) under it.

There are 2 kinds of ``MetaObject``s:
  (1) ``Element``: The basic class (leaf node).
  (2) ``Meta*``: A collection of ``MetaObject``s. It can be ``MetaDict``,
      ``MetaList`` or ``MetaSet``...etc. (non-leaf node)

      N.B. Except self-awareness of that itself is not an ``Element`` (since
      the ``is_element`` property is False), the ``Meta*`` acts the same way as
      whatever container it is. (list, dict, set...etc.)

      An easy example for ``Meta*``, say we have a ``MetaDict`` as below:
      {'a': e(1), 'b': {'c': e(2), 'd': e(3)}}, it is a dict of ``MetaObject``s,
      The e(1) is an ``Element`` and the {'c': e(2), 'd': e(3)} is a
      ``MetaDict``.

An usecase is in ``Predator``, ``Feature`` inherits ``Element`` and
``MetaFeature`` inherits ``MetaDict``, so for some relevant features, we can
group them together to get a ``MetaFeature``..
"""

import copy


class MetaObject(object):
  """Class that can be either one element or a collection of elements."""

  def IsElement(self):  # pragma: no cover
    return NotImplementedError()


class Element(MetaObject):
  """Element class that cannot be divided anymore."""

  @property
  def is_element(self):
    return True


class MetaDict(MetaObject):
  """Dict-like object containing a collection of ``MetaObject``s."""

  def __init__(self, value):
    """Construct a meta dict from a dict of meta objects.

    Args:
      value (dict): Dict of meta objects.
    """
    try:
      self._value = copy.deepcopy(value)
    except TypeError:  # pragma: no cover
      self._value = copy.copy(value)

  @property
  def is_element(self):
    return False

  def __getitem__(self, key):
    return self._value[key]

  def __setitem__(self, key, val):
    self._value[key] = val

  def get(self, key, default=None):
    return self._value.get(key, default)

  def __iter__(self):
    return iter(self._value)

  def __eq__(self, other):
    return self._value == other._value

  def iteritems(self):
    return self._value.iteritems()

  def itervalues(self):
    return self._value.itervalues()

  def keys(self):
    return self._value.keys()

  def values(self):
    return self._value.values()
