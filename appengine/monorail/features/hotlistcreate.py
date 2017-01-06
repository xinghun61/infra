# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet for creating new hotlists."""

import logging
import time
import re

from features import features_constants
from features import hotlist_helpers
from framework import framework_bizobj
from framework import framework_helpers
from framework import permissions
from framework import servlet
from framework import urls
from services import features_svc
from services import user_svc
from proto import api_pb2_v1


_MSG_HOTLIST_NAME_NOT_AVAIL = 'You already have a hotlist with that name.'
_MSG_MISSING_HOTLIST_NAME = 'Missing hotlist name'
_MSG_INVALID_HOTLIST_NAME = 'Invalid hotlist name'
_MSG_MISSING_HOTLIST_SUMMARY = 'Missing hotlist summary'
_MSG_INVALID_ISSUES_INPUT = 'Issues input is invalid'
_MSG_INVALID_MEMBERS_INPUT = 'One or more editor emails is not valid.'


class HotlistCreate(servlet.Servlet):
  """HotlistCreate shows a simple page with a form to create a hotlist."""

  _PAGE_TEMPLATE = 'features/hotlist-create-page.ezt'

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(HotlistCreate, self).AssertBasePermission(mr)
    if not permissions.CanCreateHotlist(mr.perms):
      raise permissions.PermissionException(
          'User is not allowed to create a hotlist.')

  def GatherPageData(self, mr):
    return {
        'user_tab_mode': 'st6',
        'initial_name': '',
        'initial_summary': '',
        'initial_description': '',
        'initial_issues': '',
        'initial_editors': '',
        'initial_privacy': 'no',
        }

  def ParseIssueRefs(self, mr, issue_refs_string):
    """Parses the string or project:issue_id pairs to return global issue_ids.

    Args:
      mr: commonly used info parsed from the request.
      issue_refs_string: a string list of project name and local_id for
          relevant issues, eg.  'monorail:1234, chromium:12345'.

    Returns:
      A list of global issue_ids.
    """
    string_pairs = [pair.strip() for pair in issue_refs_string.split(',')]
    issue_refs_tuples = [(pair.split(':')[0],
                          int(pair.split(':')[1].strip())) for pair in
                         string_pairs]
    project_names = [pair.split(':')[0] for pair in string_pairs]
    projects_dict = self.services.project.GetProjectsByName(
        mr.cnxn, project_names)
    return self.services.issue.ResolveIssueRefs(
        mr.cnxn, projects_dict, mr.project_name, issue_refs_tuples)

  def ProcessFormData(self, mr, post_data):
    """Process the hotlist create form.

    Args:
      mr: commonly used info parsed from the request.
      post_data: The post_data dict for the current request.

    Returns:
      String URL to redirect the user to after processing.
    """
    hotlist_name = post_data.get('hotlistname')
    if not hotlist_name:
      mr.errors.hotlistname = _MSG_MISSING_HOTLIST_NAME
    elif not framework_bizobj.IsValidHotlistName(hotlist_name):
      mr.errors.hotlistname = _MSG_INVALID_HOTLIST_NAME

    summary = post_data.get('summary')
    if not summary:
      mr.errors.summary = _MSG_MISSING_HOTLIST_SUMMARY

    description = post_data.get('description', '')
    issue_refs_string = post_data.get('issues')
    issue_ids = []
    if issue_refs_string:
      pattern = re.compile(features_constants.ISSUE_INPUT_REGEX)
      if pattern.match(issue_refs_string):
        issue_ids, _misses = self.ParseIssueRefs(mr, issue_refs_string)
      else:
        mr.errors.issues = _MSG_INVALID_ISSUES_INPUT

    editors = post_data.get('editors', '')
    editor_ids = []
    if editors:
      editor_emails = [
          email.strip() for email in editors.split(',')]
      try:
        editor_dict = self.services.user.LookupUserIDs(mr.cnxn, editor_emails)
        editor_ids = editor_dict.values()
      except user_svc.NoSuchUserException:
        mr.errors.editors = _MSG_INVALID_MEMBERS_INPUT

    is_private = post_data.get('is_private')

    if not mr.errors.AnyErrors():
      try:
        hotlist = self.services.features.CreateHotlist(
            mr.cnxn, hotlist_name, summary, description,
            owner_ids=[mr.auth.user_id], editor_ids=editor_ids,
            issue_ids = issue_ids, is_private=(is_private == 'yes'),
            ts=int(time.time()))
      except features_svc.HotlistAlreadyExists:
        mr.errors.hotlistname = _MSG_HOTLIST_NAME_NOT_AVAIL

    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, initial_name=hotlist_name, initial_summary=summary,
          initial_description=description, initial_issues=issue_refs_string,
          initial_editors=editors, initial_privacy=is_private)
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, hotlist_helpers.GetURLOfHotlist(
              mr.cnxn, hotlist, self.services.user),
          include_project=False)
