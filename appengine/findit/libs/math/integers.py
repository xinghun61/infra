# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


def constrain(value, min_inclusive, max_inclusive):
  """Constrain a value to a given inclusive range.

  This function is expected to be used with integers but should work with any
  comparable values.

  Args:
    value: the value to constrain.
    min_inclusive, max_inclusive: the range to constrain the value to.

  Returns:
    (constrained_value, constrained): The value after constraining, plus a
    boolean value indicating whether constraining was necessary.
  """
  assert min_inclusive <= max_inclusive
  if value < min_inclusive:
    return min_inclusive, True
  elif value > max_inclusive:
    return max_inclusive, True
  else:
    return value, False
