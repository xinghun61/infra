# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module offers a serializer for ``MetaDict``.

The ``MetaDictSerializer`` itself is a ``MetaDict``, only it is an ordered
``MetaDict`` (using an ``OrderedDict`` internally).

Factory of metadict serializer is offered - ``GetSerializer``.
What the factory does is it copies the structure of keys of a passed-in
``MetaObject`` and uses a ``key`` function to generate an ordered dict to
maintain the key orders.

Given the ``MetaDictSerializer`` we can serialize a
``MetaDict`` to a list of ``Element``s, and de-serialize a list of ``Element``s
to a ``MetaDict``.

Serialization is needed when we need an ordered traversal of a ``MetaDict``.
De-Serialization is needed when we want to construct the list back to
a ``MetaDict`` so we can have our customized grouping and keyword matching.

An usecase in ``Predator`` is, in ``loglinear`` classification model, we use
scipy to train ``meta_weight``(inherit from ``MetaDict``), the ``meta_weight``
has to be serialized to a list of floats for training, and after the training it
should be de-serialized to a ``meta_weight`` to multiply with ``meta_feature``.
"""

from collections import OrderedDict

from libs.meta_object import MetaDict


class Serializer(object):

  def ToList(self, element, default=None):
    """Serializes an ``Element`` to a list of this single element.

    Args:
      element (Element or None): The element to be serialized. If the element
        is None, return a list of one default value.
      default (Element or None) The default value to set when None element is
        provided.

    Returns:
      A list of single element.

    Raises:
      Exception: An error occurs when the passed-in meta object is not an
        ``Element`` object.
    """
    if element is None:
      return [default]

    return [element]

  def FromList(self, element_list, constructor=None):
    """De-serializes from element_list to an ``Element``.

    Args:
      element_list (list of Element): A list of ``Element`` object.
      constructor (callable): contructor of ``Element`` class.

    Returns:
      The ``Element`` object in the element_list.

    Raises:
      Exception: An error occurs when the element_list is not 1.
    """
    assert len(element_list) == self.Length(), Exception(
        'The element list should have the same length as serializer')

    constructor = constructor or (lambda x: x)
    return constructor(element_list[0])

  def Length(self):
    return 1


class MetaDictSerializer(MetaDict):
  """Class that serialize a ``MetaDict`` to a list of ``Element``s.

  This class itself is a ``MetaDict``, it has the same structure as the
  meta_dict it wants to serialize or de-serialize, and it is using a
  ``OrderedDict`` to keep track of the serializing order.
  """

  def __init__(self, value):
    super(MetaDictSerializer, self).__init__(value)
    self._length = None

  def ToList(self, meta_dict, default=None):
    """Serializes a ``MetaDict`` to a list of ``Element``s.

    Args:
      meta_dict (MetaDict or None): The element to be serialized. If meta_dict
        is None, return a list of default values.
      default (Element or None) The default value to set when None meta_dict is
        provided.

    Returns:
      A list of ``Element``s.
    """
    element_list = []
    for key, serializer in self.iteritems():
      sub_meta_dict = meta_dict.get(key) if meta_dict else None
      element_list.extend(serializer.ToList(sub_meta_dict, default=default))

    return element_list

  def FromList(self,
               element_list,
               meta_constructor=None,
               element_constructor=None):
    """De-serializes from element_list to an ``MetaDict``.

    Args:
      element_list (list of Element): A list of ``Element`` object.
      element_constructor (callable): The constructor of ``Element`` object that
        takes one value in element_list as input.
      meta_constructor (callable): The contructor of ``MetaDict`` object that
        only take one dict of MetaObjects as input.

    Returns:
      The ``MetaDict`` object contructed from element_list.

    Raises:
      Exception: An error occurs when the length of element_list is not equal
        to the serializer length.
    """
    assert self.Length() == len(element_list), Exception(
        'The element list should have the same length as serializer')

    meta_constructor = meta_constructor or (lambda x: x)
    meta_objs = {}
    index = 0
    for key, serializer in self.iteritems():
      # Truncate the segment in the element list to construct
      # the ``MetaObject`` corresponding to ``key``.
      segment = element_list[index:(index + serializer.Length())]
      if not hasattr(serializer, 'is_meta'):
        meta_objs[key] = serializer.FromList(segment, element_constructor)
      else:
        meta_objs[key] = serializer.FromList(segment, meta_constructor,
                                             element_constructor)

      index += serializer.Length()

    return meta_constructor(meta_objs)

  def Length(self):
    """Methods to get the length of the serializer recusively.

    Note, the length of a serializer is the number of elements, which is also
    the number of "real values" in a ``MetaDict`` structure.
    """
    if self._length is not None:
      return self._length

    self._length = 0
    for value in self.itervalues():
      self._length += value.Length()

    return self._length


def GetSerializer(meta_object, key=None):
  """Factory to get a serializer corresponding to a ``MetaObject``.

  Args:
    meta_object (MetaObject): ``Element`` or ``MetaDict`` objects.
    key (callable or None): Key function to sort ``MetaDict`` object.
  """
  if not hasattr(meta_object, 'is_meta'):
    return Serializer()

  sorted_meta = sorted(meta_object.iteritems(), key=key)
  ordered_dict = OrderedDict((key, GetSerializer(sub_meta))
                             for key, sub_meta in sorted_meta)

  return MetaDictSerializer(ordered_dict)
