# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import numpy as np
import unittest

from libs.math.vectors import vsum

BIG = 1e100
LITTLE = 1


class VectorsTest(unittest.TestCase):

  def setUp(self):
    self._xs = [BIG, LITTLE, -BIG]

  def testFsumKeepsPrecision(self):
    """Make sure ``testVsumKeepsPrecision`` should actually work.

    That is, this is a meta-test to make sure that the particular values
    of ``BIG`` and ``LITTLE`` we use will indeed behave as expected.
    """
    # N.B., with precision loss, we'll get 0 rather than LITTLE.
    self.assertEqual(LITTLE, math.fsum(self._xs))

  def testVsumKeepsPrecision(self):
    """Ensure that ``vsum`` retains precision over ``sum``.

    Because ``BIG`` is big and ``LITTLE`` is little, performing summation
    naively will cause the ``LITTLE`` to be lost in rounding errors. This
    is the same test case as ``testFsumKeepsPrecision``. We make the
    arrays have more than one element to make sure ``vsum`` actually
    does work on vectors, as intended. We use variations on ``x`` in the
    different components just so we don't do the same thing over and over;
    there's nothing special about negation or doubling.
    """
    vs = [np.array([x, -x, 2 * x]) for x in self._xs]
    total = vsum(vs)
    self.assertIsNotNone(total)

    self.assertListEqual([LITTLE, -LITTLE, 2 * LITTLE], total.tolist())

  def testVsumEmptyWithoutShape(self):
    """Ensure ``vsum`` returns ``None`` when expected.

    The empty summation should return the zero vector. However, since
    we don't know the shape of the vectors in the list, we don't know
    what shape of zero vector to return. Thus, we return ``None`` as
    the only sensible result. This test ensures that actually does happen.
    """
    self.assertIsNone(vsum([]))

  def testVsumEmptyWithShape(self):
    """Ensure ``vsum`` returns the zero vector when expected.

    The empty summation should return the zero vector. If we know the
    shape of the vectors in the list then we can in fact return the
    zero vector of the correct shape. This test ensures that actually
    does happen.
    """
    expected_shape = (3,)
    total = vsum([], shape=expected_shape)
    self.assertIsNotNone(total)
    self.assertTupleEqual(expected_shape, total.shape)
    self.assertListEqual(np.zeros(expected_shape).tolist(), total.tolist())

  def testVsumWithNonFloatVector(self):
    """Tests that ``vsum`` works for list of float-like objects."""

    class MimicFloat(object):

      def __init__(self, value):
        self.value = float(value)

      def __add__(self, number):
        return math.fsum([self.value, number])

      __radd__ = __add__

    lists = [[2.3, 0.4], [0.2, 0.3]]
    array_lists = [np.array(l) for l in lists]
    mimic_float_lists = [[MimicFloat(number) for number in l] for l in lists]
    array_mimic_float_lists = [np.array(l) for l in mimic_float_lists]

    self.assertListEqual(
        vsum(array_lists).tolist(), vsum(array_mimic_float_lists).tolist())
