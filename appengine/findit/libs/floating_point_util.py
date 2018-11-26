# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility functions for processing floating point operations."""

ABSOLUTE_TOLERANCE = 0.000001


def AlmostEquals(float_a, float_b, tolerance=ABSOLUTE_TOLERANCE):
  """Determines whether two floating points are very close to one another.

  Args:
    float_a (float): The first number to compare.
    float_b (float): The second number to compare.
    tolerance (float): The maximum allowalbe distance between the two numbers.

  Returns:
    (bool): Whether or not the two input floating points are almost equal within
        the specified tolerance.
  """
  assert float_a is not None
  assert float_b is not None

  # Add support for ints too.
  float_a = float(float_a)
  float_b = float(float_b)

  if not float_a or not float_b:
    return abs(float_a - float_b) <= tolerance

  percentage_same = (
      min(abs(float_a), abs(float_b)) / max(abs(float_a), abs(float_b)))

  import numpy  # workaround to run locally.

  return (numpy.sign(float_a) == numpy.sign(float_b) and
          1.0 - percentage_same <= tolerance)
