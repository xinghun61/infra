# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Interface of scorers to score and reason Result.

A Scorer represents a heuristic rule to score a culprit cl result.
"""

import logging


class Scorer(object):  # pragma: no cover.

  def GetMetric(self, result):
    raise NotImplementedError()

  def Score(self, metric):
    """Score the result based on extracted metric."""
    raise NotImplementedError()

  def Reason(self, metric, score):
    """Given the reason of this score."""
    raise NotImplementedError()

  def __call__(self, result):
    """Returns score and reason of this result."""
    metric = self.GetMetric(result)
    if metric is None:
      logging.warning('Cannot get needed metric of result %s for scorer %s',
                      repr(result.ToDict()), self.name)
      return 0, ''

    score = self.Score(metric)
    reason = self.Reason(metric, score)
    return score, reason

  @property
  def name(self):
    return self.__class__.__name__
