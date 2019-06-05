# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Business objects for the Monorail features.

These are classes and functions that operate on the objects that users care
about in features (eg. hotlists).
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from framework import framework_bizobj
from framework import urls
from proto import features_pb2


def GetOwnerIds(hotlist):
  """Returns the list of ids for the given hotlist's owners."""
  return hotlist.owner_ids


def UsersOwnersOfHotlists(hotlists):
  """Returns a set of all users who are owners in the given hotlists."""
  result = set()
  for hotlist in hotlists:
    result.update(hotlist.owner_ids)
  return result


def UsersInvolvedInHotlists(hotlists):
  """Returns a set of all users who have roles in the given hotlists."""
  result = set()
  for hotlist in hotlists:
    result.update(hotlist.owner_ids)
    result.update(hotlist.editor_ids)
    result.update(hotlist.follower_ids)
  return result


def UserOwnsHotlist(hotlist, effective_ids):
  """Returns T/F if the user is the owner/not the owner of the hotlist."""
  return not effective_ids.isdisjoint(hotlist.owner_ids or set())


def IssueIsInHotlist(hotlist, issue_id):
  """Returns T/F if the issue is in the hotlist."""
  return any(issue_id == hotlist_issue.issue_id
             for hotlist_issue in hotlist.items)


def UserIsInHotlist(hotlist, effective_ids):
  """Returns T/F if the user is involved/not involved in the hotlist."""
  return (UserOwnsHotlist(hotlist, effective_ids) or
          not effective_ids.isdisjoint(hotlist.editor_ids or set()) or
          not effective_ids.isdisjoint(hotlist.follower_ids or set()))


def SplitHotlistIssueRanks(target_iid, split_above, iid_rank_pairs):
  """Splits hotlist issue relation rankings by some target issue's rank.

  Args:
    target_iid: the global ID of the issue to split rankings about.
    split_above: False to split below the target issue, True to split above.
    iid_rank_pairs: a list tuples [(issue_id, rank_in_hotlist),...} for all
    issues in a hotlist excluding the one being moved.

  Returns:
    A tuple (lower, higher) where both are lists of [(issue_iid, rank), ...]
    of issues in rank order. If split_above is False the target issue is
    included in higher, otherwise it is included in lower.
  """
  iid_rank_pairs.reverse()
  offset = int(split_above)
  for i, (issue_id, _) in enumerate(iid_rank_pairs):
    if issue_id == target_iid:
      return iid_rank_pairs[:i + offset], iid_rank_pairs[i + offset:]
  logging.error(
      'Target issue %r was not found in the list of issue_id rank pairs',
                target_iid)
  return iid_rank_pairs, []


def DetermineHotlistIssuePosition(issue, issue_ids):
  """Find position of an issue in a hotlist for a flipper.

  Args:
    issue: The issue PB currently being viewed
    issue_ids: list of issue_id's

  Returns:
    A 3-tuple (prev_iid, index, next_iid) where prev_iid is the
    IID of the previous issue in the total ordering (or None),
    index is the index that the current issue has in the sorted
    list of issues in the hotlist,
    next_iid is the next issue (or None).
  """

  prev_iid, next_iid = None, None
  total_issues = len(issue_ids)
  for i, issue_id in enumerate(issue_ids):
    if issue_id == issue.issue_id:
      index = i
      if i < total_issues - 1:
        next_iid = issue_ids[i + 1]
      if i > 0:
        prev_iid = issue_ids[i - 1]
      return prev_iid, index, next_iid
  return None, None, None
