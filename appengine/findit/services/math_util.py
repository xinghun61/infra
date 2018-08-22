# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility functions for math calculations."""

from math import sqrt

from dto.float_range import FloatRange
from libs.math import statistics


def CalculateOverlapInIntervals(range_1, range_2):
  """Measures the amount of overlap between two floating point intervals.

  Args:
    range_1 (FloatRange): The first floating point range to compare.
    range_2 (FloatRange): The second floating point range to compare.

  Returns:
    (float): The maximum proportion of either region that the other overlaps.
  """
  assert range_1.upper >= range_1.lower, (
      'Usage: ({}, {}) Lower bound must be lower than upper bound'.format(
          range_1.lower, range_1.upper))
  assert range_2.upper >= range_2.lower, (
      'Usage: ({}, {}) Lower bound must be lower than upper bound'.format(
          range_2.lower, range_2.upper))

  overlap_width = (
      min(range_1.upper, range_2.upper) - max(range_1.lower, range_2.lower))

  if overlap_width < 0.0:
    # There is no overlap as each interval is out of range of the other.
    return 0.0

  range_1_width = range_1.upper - range_1.lower
  range_2_width = range_2.upper - range_2.lower

  if range_1_width == 0.0 or range_2_width == 0.0:
    # At least one range is a single point overlapped by the other. Note 0 is
    # safe to compare directly using '==' here to prevent division by 0.
    return 1.0

  return max(overlap_width / range_1_width, overlap_width / range_2_width)
