# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math

LOG_ZERO = float('-inf')
LOG_ONE = 0.


def log(x):
  """Correct implementation of logarithms, taking zero to negative infinity."""
  try:
    return math.log(x)
  except ValueError:
    return LOG_ZERO


def logsumexp(xs):
  """Efficiently and accurately compute a log-domain sum.

  While ``math.log(math.fsum(math.exp(x) for x in xs)))`` accomplishes
  the same end, it requires an additional ``len(xs) - 2`` logarithms
  and introduces more opportunities for over/underflow and rounding
  errors. Thus, this function is both more efficient and more accurate.

  Args:
    xs (collection of float): the collection of log-domain numbers to be
      summed. The order of the elements doesn't matter, nor does the
      concrete type of the collection (it could be ``list``, ``set``,
      ``frozenset``, etc); the collection just needs to support ``len``,
      ``max``, and ``iter``. Because we need the maximum before we
      can start the iteration, this function requires (in principle)
      two passes over the data; therefore we cannot take an iterator nor
      generator. The length should be computed in constant time (else it
      will introduce an unnecessary third pass over the data). Ideally
      the maximum can also be computed in constant time (in which case
      this function only needs to pass over the data once), though none
      of Python's builtin types support that.

  Returns:
    The log-domain sum of ``xs``.
  """
  if not xs:
    return LOG_ZERO

  maximum = max(xs)
  if math.isinf(maximum):
    return maximum

  total = math.fsum(math.expm1(x - maximum) for x in xs)
  return maximum + math.log1p(total + float(len(xs) - 1))
