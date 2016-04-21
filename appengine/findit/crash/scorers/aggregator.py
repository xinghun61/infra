# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Aggregator aggregates all the scorers passed in.

Multiplies scores together and combines reasons and summaries the result.
"""


class Aggregator(object):

  def __init__(self, scorers):
    self.scorers = scorers

  def ScoreAndReason(self, result):
    """Sets result.confidence and result.reason."""

    score = 1.0
    reason = ''
    for i, scorer in enumerate(self.scorers):
      current_score, current_reason = scorer(result)
      # TODO(katesonia): Compare this mutiply aggregator with a vector of scores
      # aggregator later.
      score *= current_score
      reason += '%d. %s (score: %d)\n' % (i + 1, current_reason, current_score)

    reason += '\n%s' % str(result)

    result.confidence = score
    result.reason = reason
