# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.meta_object import Element
from libs.meta_object import MetaDict


class ElementTest(unittest.TestCase):
  """Tests ``Element`` class."""

  def testIsElement(self):
    """Tests that the ``IsElement`` of ``Element`` object returns True."""
    self.assertTrue(Element().is_element)


class MetaDictTest(unittest.TestCase):
  """Tests ``MetaDict`` class."""

  def testIsElement(self):
    """Tests that the ``IsElement`` of ``MetaDict`` object returns True."""
    self.assertFalse(MetaDict({}).is_element)

  def testMetaDictGetAndSetItem(self):
    """Tests "get" and "set" item behavior of ``MetaDict``."""
    d = {'a': 1, 'b': 2, 'c': 3}
    meta_dict = MetaDict(d)
    self.assertEqual(meta_dict['a'], d['a'])
    self.assertEqual(meta_dict.get('b'), d.get('b'))
    meta_dict['a'] = 9
    d['a'] = 9
    self.assertEqual(meta_dict['a'], d['a'])

  def testMetaDictIterDict(self):
    """Tests iterating ``MetaDict``."""
    d = {'a': 1, 'b': 2, 'c': 3}
    meta_dict = MetaDict(d)
    self.assertListEqual(list(key for key in meta_dict), list(key for key in d))
    self.assertListEqual(list(meta_dict.iteritems()), list(d.iteritems()))
    self.assertListEqual(list(meta_dict.itervalues()), list(d.itervalues()))
    self.assertListEqual(meta_dict.keys(), d.keys())
    self.assertListEqual(meta_dict.values(), d.values())
    self.assertEqual(MetaDict(d), MetaDict(d))

  def testDictProperty(self):
    """Tests ``dict`` property."""
    meta_dict = MetaDict({'f1': 1})
    self.assertEqual(meta_dict.dict, {'f1': 1})

  def testFlatDictProperty(self):
    """Tests ``flat_dict`` property."""
    class MockElement(Element):
      def __init__(self, value):
        self.value = value

      def __eq__(self, other):
        return self.value == other.value

    meta_dict = MetaDict({'f1': MetaDict({'f2': MockElement(1)})})
    self.assertTrue(meta_dict.flat_dict == {'f2': MockElement(1)})

