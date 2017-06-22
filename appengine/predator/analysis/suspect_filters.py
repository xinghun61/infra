# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math


class SuspectFilter(object):
  """Filters a list of suspects."""

  def __call__(self, suspects):
    """Returns a list of suspects with impossible suspects filtered.

    Args:
      suspects (list): A list of ``Suspect``s.

    Return:
      A list of ``Suspect``s.
    """
    raise NotImplementedError()


class FilterLessLikelySuspects(SuspectFilter):
  """Filters less likely suspects.

  The "less likely" means that the suspect has less than half the probability
  of the most likely suspect.

  Note, the pass-in ``suspects`` must have their confidence computed.
  """
  def __init__(self, probability_ratio):
    if probability_ratio < 0:
      raise ValueError('Probability ratio should be non-negative.')

    self.ratio = math.log(
        float(probability_ratio)) if probability_ratio > 0 else -float('inf')

  def __call__(self, suspects):
    confidences = [suspect.confidence for suspect in suspects]
    max_score = max(confidences)
    min_score = max(min(confidences), 0.0)
    # If the probability is equally distributed, it's very possible that none of
    # them is suspect, return empty list.
    if max_score == min_score:
      return []

    filtered_suspects = []
    for suspect in suspects:  # pragma: no cover
      # The ratio of the probabilities of 2 suspects equal to
      # exp(suspect1.confidence)/exp(suspect2.confidence), so
      # suspect1.confidence - suspect2.confidence <= log(0.5) means
      # suspect1 is half as likely than suspect2.
      if (suspect.confidence <= min_score or
          suspect.confidence - max_score <= self.ratio):
        break

      filtered_suspects.append(suspect)

    return filtered_suspects
