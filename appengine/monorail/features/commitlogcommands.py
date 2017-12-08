# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Implements processing of issue update command lines.

This currently processes the leading command-lines that appear
at the top of inbound email messages to update existing issues.

It could also be expanded to allow new issues to be created. Or, to
handle commands in commit-log messages if the version control system
invokes a webhook.
"""

import logging
import re

from features import commands
from features import notify
from framework import emailfmt
from framework import exceptions
from framework import framework_bizobj
from framework import framework_helpers


# Actions have separate 'Parse' and 'Run' implementations to allow better
# testing coverage.
class IssueAction(object):
  """Base class for all issue commands."""

  def __init__(self):
    self.parser = commands.AssignmentParser(None)
    self.description = ''
    self.inbound_message = None
    self.commenter_id = None
    self.project = None
    self.config = None
    self.hostport = framework_helpers.GetHostPort()

  def Parse(
      self, cnxn, project_name, commenter_id, lines, services,
      strip_quoted_lines=False, hostport=None):
    """Populate object from raw user input."""
    self.project = services.project.GetProjectByName(cnxn, project_name)
    self.config = services.config.GetProjectConfig(
        cnxn, self.project.project_id)
    self.commenter_id = commenter_id

    # Process all valid key-value lines. Once we find a non key-value line,
    # treat the rest as the 'description'.
    for idx, line in enumerate(lines):
      valid_line = False
      m = re.match(r'^\s*(\w+)\s*\:\s*(.*?)\s*$', line)
      if m:
        # Process Key-Value
        key = m.group(1).lower()
        value = m.group(2)
        valid_line = self.parser.ParseAssignment(
            cnxn, key, value, self.config, services, self.commenter_id)

      if not valid_line:
        # Not Key-Value. Treat this line and remaining as 'description'.
        # First strip off any trailing blank lines.
        while lines and not lines[-1].strip():
          lines.pop()
        if lines:
          self.description = '\n'.join(lines[idx:])
          break

    if strip_quoted_lines:
      self.inbound_message = '\n'.join(lines)
      self.description = emailfmt.StripQuotedText(self.description)

    if hostport:
      self.hostport = hostport

    for key in ['owner_id', 'cc_add', 'cc_remove', 'summary',
                'status', 'labels_add', 'labels_remove', 'branch']:
      logging.info('\t%s: %s', key, self.parser.__dict__[key])

    for key in ['commenter_id', 'description', 'hostport']:
      logging.info('\t%s: %s', key, self.__dict__[key])

  def Run(self, cnxn, services, allow_edit=True):
    """Execute this action."""
    raise NotImplementedError()


class UpdateIssueAction(IssueAction):
  """Implements processing email replies or the "update issue" command."""

  def __init__(self, local_id):
    super(UpdateIssueAction, self).__init__()
    self.local_id = local_id

  def Run(self, cnxn, services, allow_edit=True):
    """Updates an issue based on the parsed commands."""
    try:
      issue = services.issue.GetIssueByLocalID(
          cnxn, self.project.project_id, self.local_id)
    except exceptions.NoSuchIssueException:
      return  # Issue does not exist, so do nothing

    old_owner_id = issue.owner_id
    new_summary = self.parser.summary or issue.summary

    if self.parser.status is None:
      new_status = issue.status
    else:
      new_status = self.parser.status

    if self.parser.owner_id is None:
      new_owner_id = issue.owner_id
    else:
      new_owner_id = self.parser.owner_id

    new_cc_ids = [cc for cc in list(issue.cc_ids) + list(self.parser.cc_add)
                  if cc not in self.parser.cc_remove]
    (new_labels, _update_add,
     _update_remove) = framework_bizobj.MergeLabels(
         issue.labels, self.parser.labels_add,
         self.parser.labels_remove,
         self.config.exclusive_label_prefixes)

    new_field_values = issue.field_values  # TODO(jrobbins): edit custom ones

    if not allow_edit:
      # If user can't edit, then only consider the plain-text comment,
      # and set all other fields back to their original values.
      logging.info('Processed reply from user who can not edit issue')
      new_summary = issue.summary
      new_status = issue.status
      new_owner_id = issue.owner_id
      new_cc_ids = issue.cc_ids
      new_labels = issue.labels
      new_field_values = issue.field_values

    amendments, _comment_pb = services.issue.ApplyIssueComment(
        cnxn, services, self.commenter_id,
        self.project.project_id, issue.local_id, new_summary, new_status,
        new_owner_id, new_cc_ids, new_labels, new_field_values,
        issue.component_ids, issue.blocked_on_iids, issue.blocking_iids,
        issue.dangling_blocked_on_refs, issue.dangling_blocking_refs,
        issue.merged_into, comment=self.description,
        inbound_message=self.inbound_message)

    logging.info('Updated issue %s:%s w/ amendments %r',
                 self.project.project_name, issue.local_id, amendments)

    if amendments or self.description:  # Avoid completely empty comments.
      cmnts = services.issue.GetCommentsForIssue(cnxn, issue.issue_id)
      notify.PrepareAndSendIssueChangeNotification(
          issue.issue_id, self.hostport,
          self.commenter_id, len(cmnts) - 1, old_owner_id=old_owner_id)
