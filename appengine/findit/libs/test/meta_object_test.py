# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.meta_object import MetaDict


class MetaDictTest(unittest.TestCase):
  """Tests ``MetaDict`` class."""

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

  def testLeavesProperty(self):
    """Tests ``flat_dict`` property."""
    meta_dict = MetaDict({'f1': MetaDict({'f2': 1})})
    self.assertTrue(meta_dict.leaves == {'f2': 1})

  def testIterLeaves(self):
    """Tests ``iterleaves`` method."""
    meta_dict = MetaDict({'f1': 2, 'f2': MetaDict({'f3': 1, 'f4': 9})})
    leaves = {'f1': 2, 'f3': 1, 'f4': 9}
    self.assertEqual(len(leaves), len(list(meta_dict.iterleaves())))
    for key, value in meta_dict.iterleaves():
      self.assertEqual(value, leaves[key])

  def testUpdateLeaves(self):
    """Tests ``UpdateLeaves`` method."""
    meta_dict = MetaDict({'f1': 2, 'f2': MetaDict({'f3': 1, 'f4': 9})})
    leaves = {'f1': 92, 'f3': 91}
    meta_dict.UpdateLeaves(leaves)
    for key, value in meta_dict.iterleaves():
      if key in leaves:
        self.assertEqual(value, leaves[key])

  def testTwoMetaDictEqual(self):
    """Tests ``__eq__`` and ``__ne__`` override."""
    meta_dict1 = MetaDict({'f1': 2, 'f2': MetaDict({'f3': 1, 'f4': 9})})
    meta_dict2 = MetaDict({'f1': 2, 'f2': MetaDict({'f3': 1, 'f4': 9})})
    self.assertTrue(meta_dict1 == meta_dict2)
    meta_dict2['f1'] = 3
    self.assertTrue(meta_dict1 != meta_dict2)
