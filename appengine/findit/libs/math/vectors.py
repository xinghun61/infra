# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import numpy as np


def vsum(vs, shape=None):
  """Accurate summation of a list of vectors.

  This function is like ``math.fsum`` except operating over collections
  of vectors rather than collections of scalars.

  Args:
    vs (list of np.ndarray of float): The vectors to add up.
    shape (tuple of int): the shape of the vectors. Optional.

  Returns:
    Returns an ``np.ndarray`` if all is well, otherwise returns
    ``None``. The situations where all is not well (and so we return
    ``None``) are: (1) ``vs`` is empty and ``shape`` is not provided;
    (2) a ``shape`` is provided but does not match the actual shape of
    the vectors; (3) not all the vectors in the list have the same shape.
  """
  if shape is None:
    if not vs:
      return None

    shape = vs[0].shape

  # It'd be better to vectorize the implementation of Shewchuk's
  # algorithm directly, so we can avoid needing to traverse ``vs``
  # repeatedly. However, this is deemed to have too high a maintenance
  # cost for the performance benefit.
  total = np.zeros(shape)
  it = np.nditer(total, flags=['multi_index'], op_flags=['writeonly'])
  while not it.finished:
    try:
      it[0] = math.fsum(v[it.multi_index] for v in vs)
    except TypeError:
      it[0] = sum(v[it.multi_index] for v in vs)

    it.iternext()

  return total
