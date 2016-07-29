# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the ranked issue dependency rerank functionality

Summary of classes:
  IssueRerank: Process changes to the ranking of blocked on issues
"""

import httplib
import logging
import sys

from framework import jsonfeed
from framework import monorailrequest
from framework import permissions
from tracker import tracker_helpers
from tracker import tracker_bizobj
from tracker import tracker_views


MAX_RANKING = sys.maxint
MIN_RANKING = 0


class IssueRerank(jsonfeed.JsonFeed):
  """IssueRerank is a servlet which reranks issue dependencies"""

  def AssertBasePermission(self, mr):
    super(IssueRerank, self).AssertBasePermission(mr)
    if (mr.target_id and mr.moved_ids and mr.split_above):
      parent = self.services.issue.GetIssue(mr.cnxn, mr.parent_id)
      config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
      granted_perms = tracker_bizobj.GetGrantedPerms(
          parent, mr.auth.effective_ids, config)
      edit_perm = self.CheckPerm(
          mr, permissions.EDIT_ISSUE, art=parent, granted_perms=granted_perms)
      if not edit_perm:
        raise permissions.PermissionException(
            'You are not allowed to re-rank issue dependencies.')

  def HandleRequest(self, mr):
    if not mr.parent_id:
      logging.info('No parent issue specified.')
      raise monorailrequest.InputException('No issue specified.')
    all_issues = self._GetIssues(mr)
    parent = all_issues.get(mr.parent_id)
    if not parent:
      logging.info('Parent issue not found: %d', mr.parent_id)
      raise monorailrequest.InputException('Parent issue not found.')

    open_related, closed_related = (
        tracker_helpers.GetAllowedOpenAndClosedRelatedIssues(
          self.services, mr, parent))

    changed_ranks = self._GetNewRankings(mr, all_issues, open_related)
    if changed_ranks:
      self.services.issue.ApplyIssueRerank(
          mr.cnxn, mr.parent_id, changed_ranks)
      parent = self.services.issue.GetIssue(mr.cnxn, mr.parent_id)

    blocked_on_issues = [
        tracker_views.IssueRefView(
            mr.project_name, issue_id,
            open_related, closed_related)
        for issue_id in parent.blocked_on_iids]
    dangling_blocked_on_issues = [
        tracker_views.DanglingIssueRefView(ref.project, ref.issue_id)
        for ref in parent.dangling_blocked_on_refs]
    issues = [{
          'display_name': issue.display_name,
          'issue_id': issue.issue_id,
          'issue_ref': issue.issue_ref,
          'summary': issue.summary,
          'url': issue.url,
          'is_open': issue.is_open,
          'is_dangling': False,
        } for issue in blocked_on_issues]
    issues.extend([{
        'display_name': issue.display_name,
        'issue_ref': issue.issue_ref,
        'summary': issue.summary,
        'url': issue.url,
        'is_open': issue.is_open,
        'is_dangling': True,
        } for issue in dangling_blocked_on_issues])
    return {'issues': issues}

  def _GetIssues(self, mr):
    all_issue_ids = [mr.parent_id]
    if mr.target_id:
      all_issue_ids.append(mr.target_id)
    if mr.moved_ids:
      all_issue_ids.extend(mr.moved_ids)
    return self.services.issue.GetIssuesDict(mr.cnxn, all_issue_ids)

  def _GetNewRankings(self, mr, all_issues, open_related):
    """Compute new issue reference rankings."""
    missing = False
    if not (mr.target_id):
      logging.info('No target_id.')
      missing = True
    if not (mr.moved_ids):
      logging.info('No moved_ids.')
      missing = True
    if mr.split_above is None:
      logging.info('No split_above.')
      missing = True
    if missing:
      return
    target = all_issues.get(mr.target_id)
    moved = [all_issues.get(moved_id) for moved_id in mr.moved_ids]

    if not target:
      logging.info('Target issue not found: %d.', mr.target_id)
      raise monorailrequest.InputException('Target issue not found.')
    if None in moved:
      logging.info('Invalid moved issue id(s) in %r.', mr.moved_ids)
      raise monorailrequest.InputException('Moved issue not found.')

    logging.info(
        'Moving issue(s) %r %s issue %d.',
        mr.moved_ids, 'above' if mr.split_above else 'below', mr.target_id)

    open_ids = [iid for iid in open_related.keys() if iid not in mr.moved_ids]
    lower, higher = tracker_bizobj.SplitBlockedOnRanks(
        all_issues.get(mr.parent_id), mr.target_id, mr.split_above, open_ids)
    return _GetInsertRankings(lower, higher, mr.moved_ids)

def _GetInsertRankings(lower, higher, moved_ids):
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
      return _GetInsertRankings(new_lower, new_higher, new_moved_ids)


def _DistributeRanks(low, high, rank_count):
  """Compute evenly distributed ranks in a range"""
  bucket_size = (high - low) / rank_count
  first_rank = low + (bucket_size + 1) / 2
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

