# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.meta_dict_serializer import ElementSerializer
from libs.meta_dict_serializer import GetSerializer
from libs.meta_dict_serializer import MetaDictSerializer
from libs.meta_object import Element
from libs.meta_object import MetaDict


class ElementSerializerTest(unittest.TestCase):
  """Tests that ``ElementSerializer`` works as expected."""

  def testToList(self):
    """Tests ``ToList`` method."""
    element = Element()
    element_serializer = ElementSerializer()
    self.assertListEqual(element_serializer.ToList(element), [element])
    self.assertListEqual(element_serializer.ToList(None), [None])

  def testToListRaisesException(self):
    """Tests that ``ToList`` raises exception when input is not ``Element``."""
    element_serializer = ElementSerializer()
    self.assertRaisesRegexp(
        Exception,
        'ElementSerializer can only serialize Element object.',
        element_serializer.ToList, MetaDict({}))

  def testFromList(self):
    """Tests ``FromList`` method."""
    element = Element()
    element_serializer = ElementSerializer()
    self.assertEqual(element_serializer.FromList([element], lambda x: x),
                     element)


class MockedElement(Element):

  def __init__(self, value):
    self.value = value

  def __eq__(self, other):
    return self.value == other.value

  def __ne__(self, other):
    return not self.__eq__(other)


class MockedMetaDict(MetaDict):  # pragma: no cover

  def __eq__(self, other):
    if not len(self._value) == len(other._value):
      return False

    for key, meta_object in self.iteritems():
      if meta_object != other.get(key):
        return False

    return True

  def __ne__(self, other):
    return not self.__eq__(other)


class MetaDictSerializerTest(unittest.TestCase):
  """Tests that ``MetaDictSerializer`` works as expected."""

  def testToList(self):
    """Tests ``ToList`` method."""
    meta_dict = MockedMetaDict(
        {'a': MockedMetaDict({'b': MockedElement(1), 'c': MockedElement(3)}),
         'd': MockedElement(2)})
    serializer = GetSerializer(meta_dict)
    expected_element_list = [MockedElement(1), MockedElement(3),
                             MockedElement(2)]
    element_list = serializer.ToList(meta_dict)
    for element, expected_element in zip(element_list, expected_element_list):
      self.assertEqual(element.value, expected_element.value)

  def testFromList(self):
    """Tests ``FromList`` method."""
    meta_dict = MockedMetaDict(
        {'a': MockedMetaDict({'b': MockedElement(1), 'c': MockedElement(3)}),
         'd': MockedElement(2), 'e': MockedElement(0)})
    serializer = GetSerializer(meta_dict)
    element_list = [MockedElement(1), MockedElement(3),
                    MockedElement(2), MockedElement(0)]
    self.assertTrue(meta_dict == serializer.FromList(
        element_list, meta_constructor=MockedMetaDict))
    self.assertDictEqual(serializer.FromList(element_list),
                         {'a': {'b': MockedElement(1), 'c': MockedElement(3)},
                          'd': MockedElement(2), 'e': MockedElement(0)})

  def testFromListRaisesException(self):
    """Tests ``FromList`` raises exception when lengths mismatch."""
    meta_dict = MetaDict(
        {'a': MetaDict({'b': MockedElement(1), 'c': MockedElement(3)}),
         'd': MockedElement(2), 'e': MockedElement(0)})
    serializer = GetSerializer(meta_dict)
    self.assertRaisesRegexp(
        Exception,
        'The element list should have the same length as serializer',
        serializer.FromList, [], MockedMetaDict)
