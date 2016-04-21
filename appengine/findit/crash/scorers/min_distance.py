# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""MinDistance scorer applies to MatchResult objects.

It represents a heuristic rule:
  1. Highest score if the result changed the crashed lines.
  2. 0 score if changed lines are too far away from crashed lines.
"""

import logging

from crash.scorers.scorer import Scorer

_MAX_DISTANCE = 50


class MinDistance(Scorer):

  def __init__(self, max_distance=_MAX_DISTANCE):
    self.max_distance = max_distance

  def GetMetric(self, result):
    if not hasattr(result, 'min_distance'):
      logging.warning('Scorer %s only applies to MatchResult', self.name)
      return None

    return result.min_distance

  def Score(self, min_distance):
    if min_distance > self.max_distance:
      return 0

    if min_distance == 0:
      return 1

    # TODO(katesonia): This number is randomly picked from a reasonable range,
    # best value to use still needs be experimented out.
    return 0.8

  def Reason(self, min_distance, score):
    if score == 0:
      return ''

    return 'Minimum distance to crashed line is %d' % min_distance
