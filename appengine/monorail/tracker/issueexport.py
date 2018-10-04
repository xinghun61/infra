# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet to export a range of issues in JSON format.
"""

import logging
import time

from third_party import ezt

from businesslogic import work_env
from framework import permissions
from framework import jsonfeed
from framework import servlet
from tracker import tracker_bizobj


class IssueExport(servlet.Servlet):
  """IssueExportControls let's an admin choose how to export issues."""

  _PAGE_TEMPLATE = 'tracker/issue-export-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ISSUES

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page."""
    super(IssueExport, self).AssertBasePermission(mr)
    if not mr.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
          'Only site admins may export issues')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""

    return {
        'issue_tab_mode': None,
        'initial_start': mr.start,
        'initial_num': mr.num,
        'page_perms': self.MakePagePerms(mr, None, permissions.CREATE_ISSUE),
    }


class IssueExportJSON(jsonfeed.JsonFeed):
  """IssueExport shows a range of issues in JSON format."""

  # Pretty-print the JSON output.
  JSON_INDENT = 4

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page."""
    super(IssueExportJSON, self).AssertBasePermission(mr)
    if not mr.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
          'Only site admins may export issues')

  def HandleRequest(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    if mr.query or mr.can != 1:
      with work_env.WorkEnv(mr, self.services) as we:
        url_params = []
        pipeline = we.ListIssues(mr.query, [mr.project.project_name],
                                 mr.auth.user_id, mr.num, mr.start, url_params,
                                 mr.can, mr.group_by_spec, mr.sort_spec, False)
      issues = pipeline.allowed_results
    # no user query and mr.can == 1 (we want all issues)
    elif not mr.start and not mr.num:
      issues = self.services.issue.GetAllIssuesInProject(
          mr.cnxn, mr.project.project_id)
    else:
      local_id_range = range(mr.start, mr.start + mr.num)
      issues = self.services.issue.GetIssuesByLocalIDs(
          mr.cnxn, mr.project.project_id, local_id_range)

    user_id_set = tracker_bizobj.UsersInvolvedInIssues(issues)

    comments_dict = self.services.issue.GetCommentsForIssues(
        mr.cnxn, [issue.issue_id for issue in issues])
    for comment_list in comments_dict.itervalues():
      user_id_set.update(
        tracker_bizobj.UsersInvolvedInCommentList(comment_list))

    starrers_dict = self.services.issue_star.LookupItemsStarrers(
        mr.cnxn, [issue.issue_id for issue in issues])
    for starrer_id_list in starrers_dict.itervalues():
      user_id_set.update(starrer_id_list)

    # The value 0 indicates "no user", e.g., that an issue has no owner.
    # We don't need to create a User row to represent that.
    user_id_set.discard(0)
    # TODO(jojwang): update this to handle exceptions.NoSuchUserException()
    # while still returning the email_dict with found users.
    email_dict = self.services.user.LookupUserEmails(mr.cnxn, user_id_set)

    issues_json = [
      self._MakeIssueJSON(
          mr, issue, email_dict,
          comments_dict.get(issue.issue_id, []),
          starrers_dict.get(issue.issue_id, []))
      for issue in issues if not issue.deleted]

    json_data = {
        'metadata': {
            'version': 1,
            'when': int(time.time()),
            'who': mr.auth.email,
            'project': mr.project_name,
            'start': mr.start,
            'num': mr.num,
        },
        'issues': issues_json,
        # This list could be derived from the 'issues', but we provide it for
        # ease of processing.
        'emails': email_dict.values(),
    }
    return json_data

  def _MakeAmendmentJSON(self, amendment, email_dict):
    amendment_json = {
        'field': amendment.field.name,
    }
    if amendment.custom_field_name:
      amendment_json.update({'custom_field_name': amendment.custom_field_name})
    if amendment.newvalue:
      amendment_json.update({'new_value': amendment.newvalue})
    if amendment.added_user_ids:
      amendment_json.update(
          {'added_emails': [email_dict.get(user_id)
                            for user_id in amendment.added_user_ids]})
    if amendment.removed_user_ids:
      amendment_json.update(
          {'removed_emails': [email_dict.get(user_id)
                              for user_id in amendment.removed_user_ids]})
    return amendment_json

  def _MakeAttachmentJSON(self, attachment):
    if attachment.deleted:
      return None
    attachment_json = {
      'name': attachment.filename,
      'size': attachment.filesize,
      'mimetype': attachment.mimetype,
      'gcs_object_id': attachment.gcs_object_id,
    }
    return attachment_json

  def _MakeCommentJSON(self, comment, email_dict):
    if comment.deleted_by:
      return None
    amendments = [self._MakeAmendmentJSON(a, email_dict)
                  for a in comment.amendments]
    attachments = [self._MakeAttachmentJSON(a)
                   for a in comment.attachments]
    comment_json = {
      'timestamp': comment.timestamp,
      'commenter': email_dict.get(comment.user_id),
      'content': comment.content,
      'amendments': [a for a in amendments if a],
      'attachments': [a for a in attachments if a],
    }
    return comment_json

  def _MakeFieldValueJSON(self, mr, field, email_dict):
    field_value_json = {
      'field': self.services.config.LookupField(
          mr.cnxn, mr.project.project_id, field.field_id)
    }
    if field.int_value:
      field_value_json['int_value'] = field.int_value
    if field.str_value:
      field_value_json['str_value'] = field.str_value
    if field.user_id:
      field_value_json['user_value'] = email_dict.get(field.user_id)
    if field.date_value:
      field_value_json['date_value'] = field.date_value
    return field_value_json

  def _MakeIssueJSON(
        self, mr, issue, email_dict, comment_list, starrer_id_list):
    """Return a dict of info about the issue and its comments."""
    comments = [self._MakeCommentJSON(c, email_dict) for c in comment_list]
    issue_json = {
        'local_id': issue.local_id,
        'reporter': email_dict.get(issue.reporter_id),
        'summary': issue.summary,
        'owner': email_dict.get(issue.owner_id),
        'status': issue.status,
        'cc': [email_dict[cc_id] for cc_id in issue.cc_ids],
        'labels': issue.labels,
        'fields': [self._MakeFieldValueJSON(mr, field, email_dict)
                   for field in issue.field_values],
        'starrers': [email_dict[starrer] for starrer in starrer_id_list],
        'comments': [c for c in comments if c],
        'opened': issue.opened_timestamp,
        'modified': issue.modified_timestamp,
        'closed': issue.closed_timestamp,
    }
    # TODO(agable): Export cross-project references as well.
    if issue.blocked_on_iids:
      issue_json['blocked_on'] = [i.local_id for i in
           self.services.issue.GetIssues(mr.cnxn, issue.blocked_on_iids)
           if i.project_id == mr.project.project_id]
    if issue.blocking_iids:
      issue_json['blocking'] = [i.local_id for i in
           self.services.issue.GetIssues(mr.cnxn, issue.blocking_iids)
           if i.project_id == mr.project.project_id]
    if issue.merged_into:
      merge = self.services.issue.GetIssue(mr.cnxn, issue.merged_into)
      if merge.project_id == mr.project.project_id:
        issue_json['merged_into'] = merge.local_id
    return issue_json
