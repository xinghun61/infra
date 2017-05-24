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

from framework import jsonfeed
from framework import monorailrequest
from framework import permissions
from tracker import rerank_helpers
from tracker import tracker_helpers
from tracker import tracker_bizobj
from tracker import tracker_views


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

    blocked_on_issues = self.services.issue.GetIssuesDict(
        mr.cnxn, parent.blocked_on_iids)
    blocked_on_irvs = [
        tracker_views.IssueRefView(
            mr.project_name, blocked_on_issues.get(issue_id),
            open_related, closed_related)
        for issue_id in parent.blocked_on_iids]
    dangling_blocked_on_irvs = [
        tracker_views.DanglingIssueRefView(ref.project, ref.issue_id)
        for ref in parent.dangling_blocked_on_refs]
    issues = [{
          'display_name': irv.display_name,
          'issue_id': irv.issue_id,
          'issue_ref': irv.issue_ref,
          'summary': irv.summary,
          'url': irv.url,
          'is_open': irv.is_open,
          'is_dangling': False,
        } for irv in blocked_on_irvs if irv.visible]
    issues.extend([{
        'display_name': irv.display_name,
        'issue_ref': irv.issue_ref,
        'summary': irv.summary,
        'url': irv.url,
        'is_open': irv.is_open,
        'is_dangling': True,
        } for irv in dangling_blocked_on_irvs if irv.visible])
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
    return rerank_helpers.GetInsertRankings(lower, higher, mr.moved_ids)
