# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility functions for math calculations."""

import logging
from math import sqrt

from dto.float_range import FloatRange

_ALPHA_TO_Z = {
    # Generated using scipy.stats.norm.ppf(1 - alpha).
    0.0001: 3.7190164854557088,
    0.0005: 3.2905267314919255,
    0.001: 3.0902323061678132,
    0.005: 2.5758293035489004,
    0.01: 2.3263478740408408,
    0.05: 1.6448536269514722,
    0.1: 1.2815515655446004,
}


def _GetZFromAlpha(alpha):
  """Gets a z score given alpha.

    Libraries used to compute z score may not be available in Appengine. Alpha
    values not in _ALPHA_TO_Z will be rounded to the nearest available.

  Args:
    alpha (float): The desired alpha value.

  Returns:
    z (float): The corresponding z value to the nearest alpha.
  """
  assert alpha > 0, 'Usage: Alpha must be > 0'

  if not alpha in _ALPHA_TO_Z:
    precomputed_alpha = min(_ALPHA_TO_Z.keys(), key=lambda x: abs(x - alpha))
    logging.warning(
        'Precomputed z value for alpha %s unavailable. Falling back to nearest '
        'alpha %s' % (alpha, precomputed_alpha))
    return _ALPHA_TO_Z[precomputed_alpha]

  return _ALPHA_TO_Z[alpha]


def WilsonScoreConfidenceInterval(pass_rate, iterations, alpha):
  """Determines the possible range a pass rate is likely to span.

    https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval
  Args:
    pass_rate (float): The observed number of times a test was measured to have
        passed divided by number of iterations.
    iterations (int): The number of times the test was run.
    alpha (float): The confidence level of uncertainty of the result. For
        example, a confidence level of 95% would have an alpha of 5%, or 0.05.
  Returns:
    (FloatRange): The lower and upper bounds of possible pass rates that the
        measured pass rate is likely to span given alpha.
  """
  assert iterations, 'Usage: iterations must be > 0'

  z = _GetZFromAlpha(alpha)

  center = (pass_rate + z**2 / (2 * iterations)) / (1 + z**2 / iterations)
  distance = (z / (1 + z**2 / iterations)) * sqrt(
      pass_rate * (1 - pass_rate) / iterations + z**2 / (4 * iterations**2))
  return FloatRange(lower=(center - distance), upper=(center + distance))
