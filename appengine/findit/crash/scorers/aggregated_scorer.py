# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Aggregated scorer which uses aggregators to aggregate results from
different scorers."""

from crash.scorers import aggregators


class AggregatedScorer(object):

  def __init__(self, scorers):
    self.scorers = scorers

  def Score(self, result,
            score_aggregator=aggregators.Multiplier(),
            reasons_aggregator=aggregators.IdentityAggregator(),
            changed_files_aggregator=aggregators.ChangedFilesAggregator()):
    """Aggregates score, reasons and changed_files from all the scorers.

    Note: This method sets confidence, reasons and changed_files of results.
    """
    # Transforms array of [(score1, reason1, changed_files1), (score2, reason2,
    # changed_files2)] to [(score1, score2), (reason1, reason2),
    # (changed_files1, changed_files2)] for aggregators to aggregate.
    scores, reasons, changed_files = zip(*[
        scorer(result) for scorer in self.scorers])

    result.confidence = score_aggregator(list(scores))
    result.reasons = reasons_aggregator(list(reasons))
    result.changed_files = changed_files_aggregator(list(changed_files))

    return result.confidence, result.reasons, result.changed_files
