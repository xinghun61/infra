# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the issue detail page and related forms.

Summary of classes:
  IssueDetailEzt: Show one issue in detail w/ all metadata and comments, and
               process additional comments or metadata changes on it.
  FlagSpamForm: Record the user's desire to report the issue as spam.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import httplib
import json
import logging
import time
from third_party import ezt

import settings
from api import converters
from businesslogic import work_env
from features import features_bizobj
from features import send_notifications
from features import hotlist_helpers
from features import hotlist_views
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import jsonfeed
from framework import paginate
from framework import permissions
from framework import servlet
from framework import servlet_helpers
from framework import sorting
from framework import sql
from framework import template_helpers
from framework import urls
from framework import xsrf
from proto import user_pb2
from proto import tracker_pb2
from services import features_svc
from services import tracker_fulltext
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
from tracker import tracker_views

from google.protobuf import json_format


def CheckMoveIssueRequest(
    services, mr, issue, move_selected, move_to, errors):
  """Process the move issue portions of the issue update form.

  Args:
    services: A Services object
    mr: commonly used info parsed from the request.
    issue: Issue protobuf for the issue being moved.
    move_selected: True if the user selected the Move action.
    move_to: A project_name or url to move this issue to or None
      if the project name wasn't sent in the form.
    errors: The errors object for this request.

    Returns:
      The project pb for the project the issue will be moved to
      or None if the move cannot be performed. Perhaps because
      the project does not exist, in which case move_to and
      move_to_project will be set on the errors object. Perhaps
      the user does not have permission to move the issue to the
      destination project, in which case the move_to field will be
      set on the errors object.
  """
  if not move_selected:
    return None

  if not move_to:
    errors.move_to = 'No destination project specified'
    errors.move_to_project = move_to
    return None

  if issue.project_name == move_to:
    errors.move_to = 'This issue is already in project ' + move_to
    errors.move_to_project = move_to
    return None

  move_to_project = services.project.GetProjectByName(mr.cnxn, move_to)
  if not move_to_project:
    errors.move_to = 'No such project: ' + move_to
    errors.move_to_project = move_to
    return None

  # permissions enforcement
  if not servlet_helpers.CheckPermForProject(
      mr, permissions.EDIT_ISSUE, move_to_project):
    errors.move_to = 'You do not have permission to move issues to project'
    errors.move_to_project = move_to
    return None

  elif permissions.GetRestrictions(issue):
    errors.move_to = (
        'Issues with Restrict labels are not allowed to be moved.')
    errors.move_to_project = ''
    return None

  return move_to_project


def _ComputeBackToListURL(mr, issue, config, hotlist, services):
  """Construct a URL to return the user to the place that they came from."""
  if hotlist:
    back_to_list_url = hotlist_helpers.GetURLOfHotlist(
        mr.cnxn, hotlist, services.user)
  else:
    back_to_list_url = tracker_helpers.FormatIssueListURL(
        mr, config, cursor='%s:%d' % (issue.project_name, issue.local_id))

  return back_to_list_url


class FlipperRedirectBase(servlet.Servlet):

  # pylint: disable=arguments-differ
  # pylint: disable=unused-argument
  def get(self, project_name=None, viewed_username=None, hotlist_id=None):
    with work_env.WorkEnv(self.mr, self.services) as we:
      hotlist_id = self.mr.GetIntParam('hotlist_id')
      current_issue = we.GetIssueByLocalID(self.mr.project_id, self.mr.local_id,
                                   use_cache=False)
      hotlist = None
      if hotlist_id:
        try:
          hotlist = self.services.features.GetHotlist(self.mr.cnxn, hotlist_id)
        except features_svc.NoSuchHotlistException:
          pass

      try:
        adj_issue = GetAdjacentIssue(we, current_issue,
            hotlist=hotlist, next_issue=self.next_handler)
        path = '/p/%s%s' % (adj_issue.project_name, urls.ISSUE_DETAIL)
        url = framework_helpers.FormatURL(
            [(name, self.mr.GetParam(name)) for
             name in framework_helpers.RECOGNIZED_PARAMS],
            path, id=adj_issue.local_id)
      except exceptions.NoSuchIssueException:
        config = we.GetProjectConfig(self.mr.project_id)
        url = _ComputeBackToListURL(self.mr, current_issue, config,
                                                 hotlist, self.services)
      self.redirect(url)


class FlipperNext(FlipperRedirectBase):
  next_handler = True


class FlipperPrev(FlipperRedirectBase):
  next_handler = False


class FlipperList(servlet.Servlet):
  # pylint: disable=arguments-differ
  # pylint: disable=unused-argument
  def get(self, project_name=None, viewed_username=None, hotlist_id=None):
    with work_env.WorkEnv(self.mr, self.services) as we:
      hotlist_id = self.mr.GetIntParam('hotlist_id')
      current_issue = we.GetIssueByLocalID(self.mr.project_id, self.mr.local_id,
                                   use_cache=False)
      hotlist = None
      if hotlist_id:
        try:
          hotlist = self.services.features.GetHotlist(self.mr.cnxn, hotlist_id)
        except features_svc.NoSuchHotlistException:
          pass

      config = we.GetProjectConfig(self.mr.project_id)

      if hotlist:
        self.mr.ComputeColSpec(hotlist)
      else:
        self.mr.ComputeColSpec(config)

      url = _ComputeBackToListURL(self.mr, current_issue, config,
                                               hotlist, self.services)
    self.redirect(url)


class FlipperIndex(jsonfeed.JsonFeed):
  """Return a JSON object of an issue's index in search.

  This is a distinct JSON endpoint because it can be expensive to compute.
  """
  CHECK_SECURITY_TOKEN = False

  def HandleRequest(self, mr):
    hotlist_id = mr.GetIntParam('hotlist_id')
    list_url = None
    with work_env.WorkEnv(mr, self.services) as we:
      if not _ShouldShowFlipper(mr, self.services):
        return {}
      issue = we.GetIssueByLocalID(mr.project_id, mr.local_id, use_cache=False)
      hotlist = None

      if hotlist_id:
        hotlist = self.services.features.GetHotlist(mr.cnxn, hotlist_id)

        if not features_bizobj.IssueIsInHotlist(hotlist, issue.issue_id):
          raise exceptions.InvalidHotlistException()

        if not permissions.CanViewHotlist(
            mr.auth.effective_ids, mr.perms, hotlist):
          raise permissions.PermissionException()

        (prev_iid, cur_index, next_iid, total_count
            ) = we.GetIssuePositionInHotlist(issue, hotlist)
      else:
        (prev_iid, cur_index, next_iid, total_count
            ) = we.FindIssuePositionInSearch(issue)

      config = we.GetProjectConfig(self.mr.project_id)

      if hotlist:
        mr.ComputeColSpec(hotlist)
      else:
        mr.ComputeColSpec(config)

      list_url = _ComputeBackToListURL(mr, issue, config, hotlist,
        self.services)

    prev_url = None
    next_url = None

    recognized_params = [(name, mr.GetParam(name)) for name in
                           framework_helpers.RECOGNIZED_PARAMS]
    if prev_iid:
      prev_issue = we.services.issue.GetIssue(mr.cnxn, prev_iid)
      path = '/p/%s%s' % (prev_issue.project_name, urls.ISSUE_DETAIL)
      prev_url = framework_helpers.FormatURL(
          recognized_params, path, id=prev_issue.local_id)

    if next_iid:
      next_issue = we.services.issue.GetIssue(mr.cnxn, next_iid)
      path = '/p/%s%s' % (next_issue.project_name, urls.ISSUE_DETAIL)
      next_url = framework_helpers.FormatURL(
          recognized_params, path, id=next_issue.local_id)

    return {
      'prev_iid': prev_iid,
      'prev_url': prev_url,
      'cur_index': cur_index,
      'next_iid': next_iid,
      'next_url': next_url,
      'list_url': list_url,
      'total_count': total_count,
    }


def _ShouldShowFlipper(mr, services):
  """Return True if we should show the flipper."""

  # Check if the user entered a specific issue ID of an existing issue.
  if tracker_constants.JUMP_RE.match(mr.query):
    return False

  # Check if the user came directly to an issue without specifying any
  # query or sort.  E.g., through crbug.com.  Generating the issue ref
  # list can be too expensive in projects that have a large number of
  # issues.  The all and open issues cans are broad queries, other
  # canned queries should be narrow enough to not need this special
  # treatment.
  if (not mr.query and not mr.sort_spec and
      mr.can in [tracker_constants.ALL_ISSUES_CAN,
                 tracker_constants.OPEN_ISSUES_CAN]):
    num_issues_in_project = services.issue.GetHighestLocalID(
        mr.cnxn, mr.project_id)
    if num_issues_in_project > settings.threshold_to_suppress_prev_next:
      return False

  return True


def GetAdjacentIssue(we, issue, hotlist=None, next_issue=False):
  """Compute next or previous issue given params of current issue.

  Args:
    we: A WorkEnv instance.
    issue: The current issue (from which to compute prev/next).
    hotlist (optional): The current hotlist.
    next_issue (bool): If True, return next, issue, else return previous issue.

  Returns:
    The adjacent issue.

  Raises:
    NoSuchIssueException when there is no adjacent issue in the list.
  """
  if hotlist:
    (prev_iid, _cur_index, next_iid, _total_count
        ) = we.GetIssuePositionInHotlist(issue, hotlist)
  else:
    (prev_iid, _cur_index, next_iid, _total_count
        ) = we.FindIssuePositionInSearch(issue)
  iid = next_iid if next_issue else prev_iid
  if iid is None:
    raise exceptions.NoSuchIssueException()
  return we.GetIssue(iid)
