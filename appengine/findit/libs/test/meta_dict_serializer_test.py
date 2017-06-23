# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.meta_dict_serializer import Serializer
from libs.meta_dict_serializer import GetSerializer
from libs.meta_dict_serializer import MetaDictSerializer
from libs.meta_object import MetaDict


class SerializerTest(unittest.TestCase):
  """Tests that ``Serializer`` works as expected."""

  def testToList(self):
    """Tests ``ToList`` method."""
    serializer = Serializer()
    self.assertListEqual(serializer.ToList(None), [None])

  def testFromList(self):
    """Tests ``FromList`` method."""
    serializer = Serializer()
    self.assertEqual(serializer.FromList([None], lambda x: x), None)


class MockedMetaDict(MetaDict):  # pragma: no cover

  def __eq__(self, other):
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
    meta_dict = MockedMetaDict({'a': MockedMetaDict({'b': 1, 'c': 3}), 'd': 2})
    serializer = GetSerializer(meta_dict)
    element_list = serializer.ToList(meta_dict)
    self.assertSetEqual(set(element_list), set(meta_dict.leaves.values()))

  def testFromList(self):
    """Tests ``FromList`` method."""
    meta_dict = MockedMetaDict({
        'a': MockedMetaDict({
            'b': 1,
            'c': 3
        }),
        'd': 2,
        'e': 0
    })
    serializer = GetSerializer(meta_dict)
    self.assertDictEqual(
        serializer.FromList(serializer.ToList(meta_dict)), meta_dict)

  def testFromListRaisesException(self):
    """Tests ``FromList`` raises exception when lengths mismatch."""
    meta_dict = MetaDict({'a': MetaDict({'b': 1, 'c': 3}), 'd': 2, 'e': 0})
    serializer = GetSerializer(meta_dict)
    self.assertRaisesRegexp(
        Exception, 'The element list should have the same length as serializer',
        serializer.FromList, [], MockedMetaDict)
