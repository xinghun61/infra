# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes and functions that implement command-line-like issue updates."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import re

from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from tracker import tracker_constants


def ParseQuickEditCommand(
    cnxn, cmd, issue, config, logged_in_user_id, services):
  """Parse a quick edit command into assignments and labels."""
  parts = _BreakCommandIntoParts(cmd)
  parser = AssignmentParser(None, easier_kv_labels=True)

  for key, value in parts:
    if key:  # A key=value assignment.
      valid_assignment = parser.ParseAssignment(
          cnxn, key, value, config, services, logged_in_user_id)
      if not valid_assignment:
        logging.info('ignoring assignment: %r, %r', key, value)

    elif value.startswith('-'):  # Removing a label.
      parser.labels_remove.append(_StandardizeLabel(value[1:], config))

    else:  # Adding a label.
      value = value.strip('+')
      parser.labels_add.append(_StandardizeLabel(value, config))

  new_summary = parser.summary or issue.summary

  if parser.status is None:
    new_status = issue.status
  else:
    new_status = parser.status

  if parser.owner_id is None:
    new_owner_id = issue.owner_id
  else:
    new_owner_id = parser.owner_id

  new_cc_ids = [cc for cc in list(issue.cc_ids) + list(parser.cc_add)
                if cc not in parser.cc_remove]
  (new_labels, _update_add,
   _update_remove) = framework_bizobj.MergeLabels(
       issue.labels, parser.labels_add, parser.labels_remove, config)

  return new_summary, new_status, new_owner_id, new_cc_ids, new_labels


ASSIGN_COMMAND_RE = re.compile(
    r'(?P<key>\w+(?:-|\w)*)(?:=|:)'
    r'(?:(?P<value1>(?:-|\+|\.|%|@|=|,|\w)+)|'
    r'"(?P<value2>[^"]+)"|'
    r"'(?P<value3>[^']+)')",
    re.UNICODE | re.IGNORECASE)

LABEL_COMMAND_RE = re.compile(
    r'(?P<label>(?:\+|-)?\w(?:-|\w)*)',
    re.UNICODE | re.IGNORECASE)


def _BreakCommandIntoParts(cmd):
  """Break a quick edit command into assignment and label parts.

  Args:
    cmd: string command entered by the user.

  Returns:
    A list of (key, value) pairs where key is the name of the field
    being assigned or None for OneWord labels, and value is the value
    to assign to it, or the whole label.  Value may begin with a "+"
    which is just ignored, or a "-" meaning that the label should be
    removed, or neither.
  """
  parts = []
  cmd = cmd.strip()
  m = True

  while m:
    m = ASSIGN_COMMAND_RE.match(cmd)
    if m:
      key = m.group('key')
      value = m.group('value1') or m.group('value2') or m.group('value3')
      parts.append((key, value))
      cmd = cmd[len(m.group(0)):].strip()
    else:
      m = LABEL_COMMAND_RE.match(cmd)
      if m:
        parts.append((None, m.group('label')))
        cmd = cmd[len(m.group(0)):].strip()

  return parts


def _ParsePlusMinusList(value):
  """Parse a string containing a series of plus/minuse values.

  Strings are seprated by whitespace, comma and/or semi-colon.

  Example:
    value = "one +two -three"
    plus = ['one', 'two']
    minus = ['three']

  Args:
    value: string containing unparsed plus minus values.

  Returns:
    A tuple of (plus, minus) string values.
  """
  plus = []
  minus = []
  # Treat ';' and ',' as separators (in addition to SPACE)
  for ch in [',', ';']:
    value = value.replace(ch, ' ')
  terms = [i.strip() for i in value.split()]
  for item in terms:
    if item.startswith('-'):
      minus.append(item.lstrip('-'))
    else:
      plus.append(item.lstrip('+'))  # optional leading '+'

  return plus, minus


class AssignmentParser(object):
  """Class to parse assignment statements in quick edits or email replies."""

  def __init__(self, template, easier_kv_labels=False):
    self.cc_list = []
    self.cc_add = []
    self.cc_remove = []
    self.owner_id = None
    self.status = None
    self.summary = None
    self.labels_list = []
    self.labels_add = []
    self.labels_remove = []
    self.branch = None

    # Accept "Anything=Anything" for quick-edit, but not in commit-log-commands
    # because it would be too error-prone when mixed with plain text comment
    # text and without autocomplete to help users triggering it via typos.
    self.easier_kv_labels = easier_kv_labels

    if template:
      if template.owner_id:
        self.owner_id = template.owner_id
      if template.summary:
        self.summary = template.summary
      if template.labels:
        self.labels_list = template.labels
      # Do not have a similar check as above for status because it could be an
      # empty string.
      self.status = template.status

  def ParseAssignment(self, cnxn, key, value, config, services, user_id):
    """Parse command-style text entered by the user to update an issue.

    E.g., The user may want to set the issue status to "reviewed", or
    set the owner to "me".

    Args:
      cnxn: connection to SQL database.
      key: string name of the field to set.
      value: string value to be interpreted.
      config: Projects' issue tracker configuration PB.
      services: connections to backends.
      user_id: int user ID of the user making the change.

    Returns:
      True if the line could be parsed as an assigment, False otherwise.
      Also, as a side-effect, the assigned values are built up in the instance
      variables of the parser.
    """
    valid_line = True

    if key == 'owner':
      if framework_constants.NO_VALUE_RE.match(value):
        self.owner_id = framework_constants.NO_USER_SPECIFIED
      else:
        try:
          self.owner_id = _LookupMeOrUsername(cnxn, value, services, user_id)
        except exceptions.NoSuchUserException:
          logging.warning('bad owner: %r when committing to project_id %r',
                          value, config.project_id)
          valid_line = False

    elif key == 'cc':
      try:
        add, remove = _ParsePlusMinusList(value)
        self.cc_add = [_LookupMeOrUsername(cnxn, cc, services, user_id)
                       for cc in add if cc]
        self.cc_remove = [_LookupMeOrUsername(cnxn, cc, services, user_id)
                          for cc in remove if cc]
        for user_id in self.cc_add:
          if user_id not in self.cc_list:
            self.cc_list.append(user_id)
        self.cc_list = [user_id for user_id in self.cc_list
                        if user_id not in self.cc_remove]
      except exceptions.NoSuchUserException:
        logging.warning('bad cc: %r when committing to project_id %r',
                        value, config.project_id)
        valid_line = False

    elif key == 'summary':
      self.summary = value

    elif key == 'status':
      if framework_constants.NO_VALUE_RE.match(value):
        self.status = ''
      else:
        self.status = _StandardizeStatus(value, config)

    elif key == 'label' or key == 'labels':
      self.labels_add, self.labels_remove = _ParsePlusMinusList(value)
      self.labels_add = [_StandardizeLabel(lab, config)
                         for lab in self.labels_add]
      self.labels_remove = [_StandardizeLabel(lab, config)
                            for lab in self.labels_remove]
      (self.labels_list, _update_add,
       _update_remove) = framework_bizobj.MergeLabels(
           self.labels_list, self.labels_add, self.labels_remove, config)

    elif (self.easier_kv_labels and
          key not in tracker_constants.RESERVED_PREFIXES and
          key and value):
      if key.startswith('-'):
        self.labels_remove.append(_StandardizeLabel(
            '%s-%s' % (key[1:], value), config))
      else:
        self.labels_add.append(_StandardizeLabel(
            '%s-%s' % (key, value), config))

    else:
      valid_line = False

    return valid_line


def _StandardizeStatus(status, config):
  """Attempt to match a user-supplied status with standard status values.

  Args:
    status: User-supplied status string.
    config: Project's issue tracker configuration PB.

  Returns:
    A canonicalized status string, that matches a standard project
    value, if found.
  """
  well_known_statuses = [wks.status for wks in config.well_known_statuses]
  return _StandardizeArtifact(status, well_known_statuses)


def _StandardizeLabel(label, config):
  """Attempt to match a user-supplied label with standard label values.

  Args:
    label: User-supplied label string.
    config: Project's issue tracker configuration PB.

  Returns:
    A canonicalized label string, that matches a standard project
    value, if found.
  """
  well_known_labels = [wkl.label for wkl in config.well_known_labels]
  return _StandardizeArtifact(label, well_known_labels)


def _StandardizeArtifact(artifact, well_known_artifacts):
  """Attempt to match a user-supplied artifact with standard artifact values.

  Args:
    artifact: User-supplied artifact string.
    well_known_artifacts: List of well known values of the artifact.

  Returns:
    A canonicalized artifact string, that matches a standard project
    value, if found.
  """
  artifact = framework_bizobj.CanonicalizeLabel(artifact)
  for wka in well_known_artifacts:
    if artifact.lower() == wka.lower():
      return wka
  # No match - use user-supplied artifact.
  return artifact


def _LookupMeOrUsername(cnxn, username, services, user_id):
  """Handle the 'me' syntax or lookup a user's user ID."""
  if username.lower() == 'me':
    return user_id

  return services.user.LookupUserID(cnxn, username)
