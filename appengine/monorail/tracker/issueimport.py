# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet to import a file of issues in JSON format.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import json
import logging
import time

from third_party import ezt

from features import filterrules_helpers
from framework import framework_helpers
from framework import jsonfeed
from framework import permissions
from framework import servlet
from framework import urls
from proto import tracker_pb2


ParserState = collections.namedtuple(
    'ParserState',
    'user_id_dict, nonexist_emails, issue_list, comments_dict, starrers_dict, '
    'relations_dict')


class IssueImport(servlet.Servlet):
  """IssueImport loads a file of issues in JSON format."""

  _PAGE_TEMPLATE = 'tracker/issue-import-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ISSUES

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page."""
    super(IssueImport, self).AssertBasePermission(mr)
    if not mr.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
          'Only site admins may import issues')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    return {
        'issue_tab_mode': None,
        'page_perms': self.MakePagePerms(mr, None, permissions.CREATE_ISSUE),
        'import_errors': [],
    }

  def ProcessFormData(self, mr, post_data):
    """Process the issue entry form.

    Args:
      mr: commonly used info parsed from the request.
      post_data: The post_data dict for the current request.

    Returns:
      String URL to redirect the user to after processing.
    """
    import_errors = []
    json_data = None

    pre_check_only = 'pre_check_only' in post_data

    uploaded_file = post_data.get('jsonfile')
    if uploaded_file is None:
      import_errors.append('No file uploaded')
    else:
      try:
        json_str = uploaded_file.value
        if json_str.startswith(jsonfeed.XSSI_PREFIX):
          json_str = json_str[len(jsonfeed.XSSI_PREFIX):]
        json_data = json.loads(json_str)
      except ValueError:
        import_errors.append('error parsing JSON in file')

    if uploaded_file and not json_data:
      import_errors.append('JSON file was empty')

    # Note that the project must already exist in order to even reach
    # this servlet because it is hosted in the context of a project.
    if json_data and mr.project_name != json_data['metadata']['project']:
      import_errors.append(
        'Project name does not match. '
        'Edit the file if you want to import into this project anyway.')

    if import_errors:
      return self.PleaseCorrect(mr, import_errors=import_errors)

    event_log = []  # We accumulate a list of messages to display to the user.

    try:
      # First we parse the JSON into objects, but we don't have DB IDs yet.
      state = self._ParseObjects(mr.cnxn, mr.project_id, json_data, event_log)
      # If that worked, go ahead and start saving the data to the DB.
      if not pre_check_only:
        self._SaveObjects(mr.cnxn, mr.project_id, state, event_log)
    except JSONImportError:
      # just report it to the user by displaying event_log
      event_log.append('Aborted import processing')

    # This is a little bit of a hack because it always uses the form validation
    # error message display logic to show the results of this import run,
    # which may include errors or not.
    return self.PleaseCorrect(mr, import_errors=event_log)

  def _ParseObjects(self, cnxn, project_id, json_data, event_log):
    """Examine JSON data and return a parser state for further processing."""
    # Decide which users need to be created.
    needed_emails = json_data['emails']
    user_id_dict = self.services.user.LookupExistingUserIDs(cnxn, needed_emails)
    nonexist_emails = [email for email in needed_emails
                       if email not in user_id_dict]

    event_log.append('Need to create %d users: %r' %
                     (len(nonexist_emails), nonexist_emails))
    user_id_dict.update({
        email.lower(): framework_helpers.MurmurHash3_x86_32(email.lower())
        for email in nonexist_emails})

    num_comments = 0
    num_stars = 0
    issue_list = []
    comments_dict = collections.defaultdict(list)
    starrers_dict = collections.defaultdict(list)
    relations_dict = collections.defaultdict(list)
    for issue_json in json_data.get('issues', []):
      issue, comment_list, starrer_list, relation_list = self._ParseIssue(
          cnxn, project_id, user_id_dict, issue_json, event_log)
      issue_list.append(issue)
      comments_dict[issue.local_id] = comment_list
      starrers_dict[issue.local_id] = starrer_list
      relations_dict[issue.local_id] = relation_list
      num_comments += len(comment_list)
      num_stars += len(starrer_list)

    event_log.append(
      'Found info for %d issues: %r' %
      (len(issue_list), sorted([issue.local_id for issue in issue_list])))

    event_log.append(
      'Found %d total comments for %d issues' %
      (num_comments, len(comments_dict)))

    event_log.append(
      'Found %d total stars for %d issues' %
      (num_stars, len(starrers_dict)))

    event_log.append(
      'Found %d total relationships.' %
      sum((len(dsts) for dsts in relations_dict.itervalues())))

    event_log.append('Parsing phase finished OK')
    return ParserState(
      user_id_dict, nonexist_emails, issue_list,
      comments_dict, starrers_dict, relations_dict)

  def _ParseIssue(self, cnxn, project_id, user_id_dict, issue_json, event_log):
    issue = tracker_pb2.Issue(
      project_id=project_id,
      local_id=issue_json['local_id'],
      reporter_id=user_id_dict[issue_json['reporter']],
      summary=issue_json['summary'],
      opened_timestamp=issue_json['opened'],
      modified_timestamp=issue_json['modified'],
      cc_ids=[user_id_dict[cc_email]
              for cc_email in issue_json.get('cc', [])
              if cc_email in user_id_dict],
      status=issue_json.get('status', ''),
      labels=issue_json.get('labels', []),
      field_values=[self._ParseFieldValue(cnxn, project_id, user_id_dict, field)
                    for field in issue_json.get('fields', [])])
    if issue_json.get('owner'):
      issue.owner_id = user_id_dict[issue_json['owner']]
    if issue_json.get('closed'):
      issue.closed_timestamp = issue_json['closed']
    comments = [self._ParseComment(
                    project_id, user_id_dict, comment_json, event_log)
                for comment_json in issue_json.get('comments', [])]

    starrers = [user_id_dict[starrer] for starrer in issue_json['starrers']]

    relations = []
    relations.extend(
        [(i, 'blockedon') for i in issue_json.get('blocked_on', [])])
    relations.extend(
        [(i, 'blocking') for i in issue_json.get('blocking', [])])
    if 'merged_into' in issue_json:
      relations.append((issue_json['merged_into'], 'mergedinto'))

    return issue, comments, starrers, relations

  def _ParseFieldValue(self, cnxn, project_id, user_id_dict, field_json):
    field = tracker_pb2.FieldValue(
        field_id=self.services.config.LookupFieldID(cnxn, project_id,
                                                    field_json['field']))
    if 'int_value' in field_json:
      field.int_value = field_json['int_value']
    if 'str_value' in field_json:
      field.str_value = field_json['str_value']
    if 'user_value' in field_json:
      field.user_value = user_id_dict.get(field_json['user_value'])

    return field

  def _ParseComment(self, project_id, user_id_dict, comment_json, event_log):
    comment = tracker_pb2.IssueComment(
        # Note: issue_id is filled in after the issue is saved.
        project_id=project_id,
        timestamp=comment_json['timestamp'],
        user_id=user_id_dict[comment_json['commenter']],
        content=comment_json.get('content'))

    for amendment in comment_json['amendments']:
      comment.amendments.append(
          self._ParseAmendment(amendment, user_id_dict, event_log))

    for attachment in comment_json['attachments']:
      comment.attachments.append(
          self._ParseAttachment(attachment, event_log))

    if comment_json['description_num']:
      comment.is_description = True

    return comment

  def _ParseAmendment(self, amendment_json, user_id_dict, _event_log):
    amendment = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID(amendment_json['field']))

    if 'new_value' in amendment_json:
      amendment.newvalue = amendment_json['new_value']
    if 'custom_field_name' in amendment_json:
      amendment.custom_field_name = amendment_json['custom_field_name']
    if 'added_users' in amendment_json:
      amendment.added_user_ids.extend(
          [user_id_dict[email] for email in amendment_json['added_users']])
    if 'removed_users' in amendment_json:
      amendment.removed_user_ids.extend(
          [user_id_dict[email] for email in amendment_json['removed_users']])

    return amendment

  def _ParseAttachment(self, attachment_json, _event_log):
    attachment = tracker_pb2.Attachment(
        filename=attachment_json['name'],
        filesize=attachment_json['size'],
        mimetype=attachment_json['mimetype'],
        gcs_object_id=attachment_json['gcs_object_id']
    )
    return attachment

  def _SaveObjects(self, cnxn, project_id, state, event_log):
    """Examine JSON data and create users, issues, and comments."""

    created_user_ids = self.services.user.LookupUserIDs(
      cnxn, state.nonexist_emails, autocreate=True)
    for created_email, created_id in created_user_ids.items():
      if created_id != state.user_id_dict[created_email]:
        event_log.append('Mismatched user_id for %r' % created_email)
        raise JSONImportError()
    event_log.append('Created %d users' % len(state.nonexist_emails))

    total_comments = 0
    total_stars = 0
    config = self.services.config.GetProjectConfig(cnxn, project_id)
    for issue in state.issue_list:
      # TODO(jrobbins): renumber issues if there is a local_id conflict.
      if issue.local_id not in state.starrers_dict:
        # Issues with stars will have filter rules applied in SetStar().
        filterrules_helpers.ApplyFilterRules(
            cnxn, self.services, issue, config)
      issue_id = self.services.issue.InsertIssue(cnxn, issue)
      for comment in state.comments_dict[issue.local_id]:
        total_comments += 1
        comment.issue_id = issue_id
        self.services.issue.InsertComment(cnxn, comment)
      self.services.issue_star.SetStarsBatch(
          cnxn, self.services, config, issue_id,
          state.starrers_dict[issue.local_id], True)
      total_stars += len(state.starrers_dict[issue.local_id])

    event_log.append('Created %d issues' % len(state.issue_list))
    event_log.append('Created %d comments for %d issues' % (
        total_comments, len(state.comments_dict)))
    event_log.append('Set %d stars on %d issues' % (
        total_stars, len(state.starrers_dict)))

    global_relations_dict = collections.defaultdict(list)
    for issue, rels in state.relations_dict.iteritems():
      src_iid = self.services.issue.GetIssueByLocalID(
          cnxn, project_id, issue).issue_id
      dst_iids = [i.issue_id for i in self.services.issue.GetIssuesByLocalIDs(
          cnxn, project_id, [rel[0] for rel in rels])]
      kinds = [rel[1] for rel in rels]
      global_relations_dict[src_iid] = list(zip(dst_iids, kinds))
    self.services.issue.RelateIssues(cnxn, global_relations_dict)

    self.services.issue.SetUsedLocalID(cnxn, project_id)
    event_log.append('Finished import')


class JSONImportError(Exception):
  """Exception to raise if imported JSON is invalid."""
  pass
