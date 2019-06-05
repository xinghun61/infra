# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Functions to help rerank issues in a lit.

This file contains methods that implement a reranking algorithm for
issues in a list.
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import sys

MAX_RANKING = sys.maxint
MIN_RANKING = 0

def GetInsertRankings(lower, higher, moved_ids):
  """Compute rankings for moved_ids to insert between the
  lower and higher rankings

  Args:
    lower: a list of [(id, rank),...] of blockers that should have
      a lower rank than the moved issues. Should be sorted from highest
      to lowest rank.
    higher: a list of [(id, rank),...] of blockers that should have
      a higher rank than the moved issues. Should be sorted from highest
      to lowest rank.
    moved_ids: a list of global IDs for issues to re-rank.

  Returns:
    a list of [(id, rank),...] of blockers that need to be updated. rank
    is the new rank of the issue with the specified id.
  """
  if lower:
    lower_rank = lower[-1][1]
  else:
    lower_rank = MIN_RANKING

  if higher:
    higher_rank = higher[0][1]
  else:
    higher_rank = MAX_RANKING

  slot_count = higher_rank - lower_rank - 1
  if slot_count >= len(moved_ids):
    new_ranks = _DistributeRanks(lower_rank, higher_rank, len(moved_ids))
    return zip(moved_ids, new_ranks)
  else:
    new_lower, new_higher, new_moved_ids = _ResplitRanks(
        lower, higher, moved_ids)
    if not new_moved_ids:
      return None
    else:
      return GetInsertRankings(new_lower, new_higher, new_moved_ids)


def _DistributeRanks(low, high, rank_count):
  """Compute evenly distributed ranks in a range"""
  bucket_size = (high - low) // rank_count
  first_rank = low + (bucket_size + 1) // 2
  return range(first_rank, high, bucket_size)


def _ResplitRanks(lower, higher, moved_ids):
  if not (lower or higher):
    return None, None, None

  if not lower:
    take_from = 'higher'
  elif not higher:
    take_from = 'lower'
  else:
    next_lower = lower[-2][1] if len(lower) >= 2 else MIN_RANKING
    next_higher = higher[1][1] if len(higher) >= 2 else MAX_RANKING
    if (lower[-1][1] - next_lower) > (next_higher - higher[0][1]):
      take_from = 'lower'
    else:
      take_from = 'higher'

  if take_from == 'lower':
    return (lower[:-1], higher, [lower[-1][0]] + moved_ids)
  else:
    return (lower, higher[1:], moved_ids + [higher[0][0]])
