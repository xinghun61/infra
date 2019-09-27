# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Implements processing of issue update command lines.

This currently processes the leading command-lines that appear
at the top of inbound email messages to update existing issues.

It could also be expanded to allow new issues to be created. Or, to
handle commands in commit-log messages if the version control system
invokes a webhook.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import re

from businesslogic import work_env
from features import commands
from features import send_notifications
from framework import emailfmt
from framework import exceptions
from framework import framework_bizobj
from framework import framework_helpers
from framework import permissions
from proto import tracker_pb2


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
    """Populate object from raw user input.

    Args:
      cnxn: connection to SQL database.
      project_name: Name of the project containing the issue.
      commenter_id: int user ID of user creating comment.
      lines: list of strings containing test to be parsed.
      services: References to existing objects from Monorail's service layer.
      strip_quoted_lines: boolean for whether to remove quoted lines from text.
      hostport: Optionally override the current instance's hostport variable.

    Returns:
      A boolean for whether any command lines were found while parsing.

    Side-effect:
      Edits the values of instance variables in this class with parsing output.
    """
    self.project = services.project.GetProjectByName(cnxn, project_name)
    self.config = services.config.GetProjectConfig(
        cnxn, self.project.project_id)
    self.commenter_id = commenter_id

    has_commands = False

    # Process all valid key-value lines. Once we find a non key-value line,
    # treat the rest as the 'description'.
    for idx, line in enumerate(lines):
      valid_line = False
      m = re.match(r'^\s*(\w+)\s*\:\s*(.*?)\s*$', line)
      if m:
        has_commands = True
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

    return has_commands

  def Run(self, mc, services):
    """Execute this action."""
    raise NotImplementedError()


class UpdateIssueAction(IssueAction):
  """Implements processing email replies or the "update issue" command."""

  def __init__(self, local_id):
    super(UpdateIssueAction, self).__init__()
    self.local_id = local_id

  def Run(self, mc, services):
    """Updates an issue based on the parsed commands."""
    try:
      issue = services.issue.GetIssueByLocalID(
          mc.cnxn, self.project.project_id, self.local_id, use_cache=False)
    except exceptions.NoSuchIssueException:
      return  # Issue does not exist, so do nothing

    delta = tracker_pb2.IssueDelta()

    allow_edit = permissions.CanEditIssue(
        mc.auth.effective_ids, mc.perms, self.project, issue)

    if allow_edit:
      delta.summary = self.parser.summary or issue.summary
      if self.parser.status is None:
        delta.status = issue.status
      else:
        delta.status = self.parser.status

      if self.parser.owner_id is None:
        delta.owner_id = issue.owner_id
      else:
        delta.owner_id = self.parser.owner_id

      delta.cc_ids_add = list(self.parser.cc_add)
      delta.cc_ids_remove = list(self.parser.cc_remove)
      delta.labels_add = self.parser.labels_add
      delta.labels_remove = self.parser.labels_remove
      # TODO(jrobbins): allow editing of custom fields

    with work_env.WorkEnv(mc, services) as we:
      we.UpdateIssue(
          issue, delta, self.description, inbound_message=self.inbound_message)

    logging.info('Updated issue %s:%s',
                 self.project.project_name, issue.local_id)

    # Note: notifications are generated in work_env.
