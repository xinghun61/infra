# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet to show the original email that caused an issue comment.

The text of the body the email is shown in an HTML page with <pre>.
All the text is automatically escaped by EZT to make it safe to
include in an HTML page.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
from third_party import ezt

from businesslogic import work_env
from framework import filecontent
from framework import permissions
from framework import servlet
from services import issue_svc


class IssueOriginal(servlet.Servlet):
  """IssueOriginal shows an inbound email that caused an issue comment."""

  _PAGE_TEMPLATE = 'tracker/issue-original-page.ezt'

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page."""
    super(IssueOriginal, self).AssertBasePermission(mr)
    issue, comment = self._GetIssueAndComment(mr)

    # TODO(jrobbins): take granted perms into account here.
    if issue and not permissions.CanViewIssue(
        mr.auth.effective_ids, mr.perms, mr.project, issue,
        allow_viewing_deleted=True):
      raise permissions.PermissionException(
          'User is not allowed to view this issue')

    can_view_inbound_message = self.CheckPerm(
        mr, permissions.VIEW_INBOUND_MESSAGES, art=issue)
    issue_perms = permissions.UpdateIssuePermissions(
        mr.perms, mr.project, issue, mr.auth.effective_ids)
    commenter = self.services.user.GetUser(mr.cnxn, comment.user_id)
    can_view_comment = permissions.CanViewComment(
        comment, commenter, mr.auth.user_id, issue_perms)
    if not can_view_inbound_message or not can_view_comment:
      raise permissions.PermissionException(
          'Only project members may view original email text')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    issue, comment = self._GetIssueAndComment(mr)
    message_body_unicode, is_binary, _is_long = (
        filecontent.DecodeFileContents(comment.inbound_message))

    # Take out the iso8859-1 non-breaking-space characters that gmail
    # inserts between consecutive spaces when quoting text in a reply.
    # You can see this in gmail by sending a plain text reply to a
    # message that had multiple spaces on some line, then use the
    # "Show original" menu item to view your reply, you will see "=A0".
    #message_body_unicode = message_body_unicode.replace(u'\xa0', u' ')

    page_data = {
        'local_id': issue.local_id,
        'seq': comment.sequence,
        'is_binary': ezt.boolean(is_binary),
        'message_body': message_body_unicode,
        }

    return page_data

  def _GetIssueAndComment(self, mr):
    """Wait on retriving the specified issue and issue comment."""
    if mr.seq is None:
      self.abort(404, 'comment not specified')

    with work_env.WorkEnv(mr, self.services) as we:
      issue = self.services.issue.GetIssueByLocalID(
          mr.cnxn, mr.project_id, mr.local_id)
      comments = we.ListIssueComments(issue)

    try:
      comment = comments[mr.seq]
    except IndexError:
      self.abort(404, 'comment not found')

    return issue, comment
