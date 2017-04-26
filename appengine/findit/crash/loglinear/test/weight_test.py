# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from crash.loglinear.feature import MetaFeatureValue
from crash.loglinear.weight import MetaWeight
from crash.loglinear.weight import Weight


class WeightTest(unittest.TestCase):
  """Tests class ``Weight``."""

  def testFloat(self):
    """Tests convert ``Weight`` to float."""
    self.assertEqual(float(Weight(0.8)), 0.8)

  def testMultiply(self):
    """Tests overloading operators ``__mul__`` and ``__rmul__``"""
    self.assertEqual((Weight(0.8) * 2.0), 0.8 * 2.0)
    self.assertEqual((2.0 * Weight(0.8)), 2.0 * 0.8)

  def testEqual(self):
    """Tests ``__eq__`` and ``__ne__``."""
    self.assertTrue(Weight(0.2) == Weight(0.2))
    self.assertTrue(Weight(0.2) != Weight(0.3))

  def testIsZero(self):
    """Tests ``IsZero`` method."""
    self.assertTrue(Weight(0.00001).IsZero(0.001))
    self.assertFalse(Weight(0.00001).IsZero(0.000001))

  def testLen(self):
    """Tests overloading operator ``__len__``."""
    self.assertEqual(len(Weight(0.5)), 1)

  def testl0(self):
    """Tests ``l0`` property."""
    self.assertEqual(Weight(0.2).l0, 1)
    self.assertEqual(Weight(0.).l0, 0)

  def testl1(self):
    """Tests ``l1`` property."""
    self.assertEqual(Weight(0.3).l1, 0.3)
    self.assertEqual(Weight(-0.3).l1, 0.3)

  def testquadrance(self):
    """Tests ``quadrance`` property."""
    self.assertEqual(Weight(0.3).quadrance, 0.09)
    self.assertEqual(Weight(-0.3).quadrance, 0.09)


class MetaWeightTest(unittest.TestCase):
  """Tests class ``MetaWeight``."""

  def testMultiply(self):
    """Tests overloading operators ``__mul__`` and ``__rmul__``"""
    self.assertEqual(MetaWeight({'f1': Weight(0.8), 'f2': Weight(0.4)}) *
                     MetaFeatureValue('f', {'f1': 2., 'f2': 1.}), 2.)
    self.assertEqual(MetaFeatureValue('f', {'f1': 0.8, 'f2': 0.4}) *
                     MetaWeight({'f1': Weight(2.), 'f2': Weight(1.)}), 2.)

    self.assertEqual(
        MetaWeight({'f1': Weight(0.8), 'f3': Weight(0.0)}) *
        MetaFeatureValue('f', {'f1': Weight(2.), 'f2': Weight(9),
                               'f3': Weight(10)}),
        1.6)

  def testIter(self):
    """Tests overloading operator ``__iter__``."""
    weights = {'a': Weight(0.2), 'b': Weight(0.4), 'c': Weight(3.2)}
    meta_weight = MetaWeight(weights)
    self.assertSetEqual(set(iter(meta_weight)), set(iter(weights)))
    for key, value in meta_weight.iteritems():
      self.assertEqual(value, weights[key])

  def testLen(self):
    """Tests overloading operator ``__len__``."""
    self.assertEqual(len(MetaWeight({'a': Weight(0.5), 'b': Weight(0.23)})), 2)

  def testIsZero(self):
    """Tests ``IsZero`` method."""
    self.assertTrue(MetaWeight({'f1': Weight(0.008),
                                'f2': Weight(0.00004)}).IsZero(0.01))
    self.assertFalse(MetaWeight({'f1': Weight(0.08),
                                 'f2': Weight(0.00004)}).IsZero(0.001))

  def testEqual(self):
    """Tests ``__eq__`` and ``__ne__``."""
    self.assertTrue(MetaWeight({'f1': Weight(0.008)}) ==
                    MetaWeight({'f1': Weight(0.008)}))
    self.assertFalse(MetaWeight({'f1': MetaWeight({'f2': Weight(0.008)})}) ==
                    MetaWeight({'f1': MetaWeight({'f2': Weight(0.1)})}))
    self.assertFalse(MetaWeight({'f1': Weight(0.008)}) ==
                    MetaWeight({}))

  def testDropZeroWeights(self):
    meta_weight = MetaWeight({'f1': Weight(0.02),
                              'f2': MetaWeight({'f3': Weight(0.00001),
                                                'f4': Weight(0.0000003)})})
    meta_weight.DropZeroWeights(epsilon=0.0001)
    expected_meta_weight = MetaWeight({'f1': Weight(0.02)})
    self.assertTrue(meta_weight == expected_meta_weight)

  def testl0(self):
    """Tests ``l0`` property."""
    self.assertEqual(MetaWeight({'a': Weight(0.2), 'b': Weight(0.),
                                 'd': Weight(0.), 'e': Weight(2.)}).l0, 2)
    self.assertEqual(MetaWeight({'a': Weight(0.), 'b': Weight(0.)}).l0, 0)

  def testl1(self):
    """Tests ``l1`` property."""
    self.assertEqual(MetaWeight({'a': Weight(0.3), 'b': Weight(0.2)}).l1, 0.5)
    self.assertEqual(MetaWeight({'a': Weight(0.3), 'b': Weight(-0.3)}).l1, 0.6)

  def testquadrance(self):
    """Tests ``quadrance`` property."""
    self.assertEqual(MetaWeight({'a': Weight(0.3),
                                 'b': Weight(0.2)}).quadrance, 0.13)
    self.assertEqual(MetaWeight({'a': Weight(0.3),
                                 'b': Weight(-0.3)}).quadrance, 0.18)
