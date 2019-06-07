# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Business objects for Monorail's framework.

These are classes and functions that operate on the objects that
users care about in Monorail but that are not part of just one specific
component: e.g., projects, users, and labels.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import re
import string

import settings
from framework import framework_constants
from proto import tracker_pb2


# Pattern to match a valid project name.  Users of this pattern MUST use
# the re.VERBOSE flag or the whitespace and comments we be considered
# significant and the pattern will not work.  See "re" module documentation.
_RE_PROJECT_NAME_PATTERN_VERBOSE = r"""
  (?=[-a-z0-9]*[a-z][-a-z0-9]*)   # Lookahead to make sure there is at least
                                  # one letter in the whole name.
  [a-z0-9]                        # Start with a letter or digit.
  [-a-z0-9]*                      # Follow with any number of valid characters.
  [a-z0-9]                        # End with a letter or digit.
"""


# Compiled regexp to match the project name and nothing more before or after.
RE_PROJECT_NAME = re.compile(
    '^%s$' % _RE_PROJECT_NAME_PATTERN_VERBOSE, re.VERBOSE)


def IsValidProjectName(s):
  """Return true if the given string is a valid project name."""
  return (RE_PROJECT_NAME.match(s) and
          len(s) <= framework_constants.MAX_PROJECT_NAME_LENGTH)


def UserOwnsProject(project, effective_ids):
  """Return True if any of the effective_ids is a project owner."""
  return not effective_ids.isdisjoint(project.owner_ids or set())


def UserIsInProject(project, effective_ids):
  """Return True if any of the effective_ids is a project member.

  Args:
    project: Project PB for the current project.
    effective_ids: set of int user IDs for the current user (including all
        user groups).  This will be an empty set for anonymous users.

  Returns:
    True if the user has any direct or indirect role in the project.  The value
    will actually be a set(), but it will have an ID in it if the user is in
    the project, or it will be an empty set which is considered False.
  """
  return (UserOwnsProject(project, effective_ids) or
          not effective_ids.isdisjoint(project.committer_ids or set()) or
          not effective_ids.isdisjoint(project.contributor_ids or set()))


def AllProjectMembers(project):
  """Return a list of user IDs of all members in the given project."""
  return project.owner_ids + project.committer_ids + project.contributor_ids


def IsPriviledgedDomainUser(email):
  """Return True if the user's account is from a priviledged domain."""
  if email and '@' in email:
    _, user_domain = email.split('@', 1)
    return user_domain in settings.priviledged_user_domains

  return False


# String translation table to catch a common typos in label names.
_CANONICALIZATION_TRANSLATION_TABLE = {
    ord(delete_u_char): None
    for delete_u_char in u'!"#$%&\'()*+,/:;<>?@[\\]^`{|}~\t\n\x0b\x0c\r '
    }
_CANONICALIZATION_TRANSLATION_TABLE.update({ord(u'='): ord(u'-')})


def CanonicalizeLabel(user_input):
  """Canonicalize a given label or status value.

  When the user enters a string that represents a label or an enum,
  convert it a canonical form that makes it more likely to match
  existing values.

  Args:
    user_input: string that the user typed for a label.

  Returns:
    Canonical form of that label as a unicode string.
  """
  if user_input is None:
    return user_input

  if not isinstance(user_input, unicode):
    user_input = user_input.decode('utf-8')

  canon_str = user_input.translate(_CANONICALIZATION_TRANSLATION_TABLE)
  return canon_str


def MergeLabels(labels_list, labels_add, labels_remove, config):
  """Update a list of labels with the given add and remove label lists.

  Args:
    labels_list: list of current labels.
    labels_add: labels that the user wants to add.
    labels_remove: labels that the user wants to remove.
    config: ProjectIssueConfig with info about exclusive prefixes and
        enum fields.

  Returns:
    (merged_labels, update_labels_add, update_labels_remove):
    A new list of labels with the given labels added and removed, and
    any exclusive label prefixes taken into account.  Then two
    lists of update strings to explain the changes that were actually
    made.
  """
  old_lower_labels = [lab.lower() for lab in labels_list]
  labels_add = [lab for lab in labels_add
                if lab.lower() not in old_lower_labels]
  labels_remove = [lab for lab in labels_remove
                   if lab.lower() in old_lower_labels]
  labels_remove_lower = [lab.lower() for lab in labels_remove]
  exclusive_prefixes = [
      lab.lower() + '-' for lab in config.exclusive_label_prefixes]
  for fd in config.field_defs:
    if (fd.field_type == tracker_pb2.FieldTypes.ENUM_TYPE and
        not fd.is_multivalued):
      exclusive_prefixes.append(fd.field_name.lower() + '-')

  # We match prefix strings rather than splitting on dash because
  # an exclusive-prefix or field name may contain dashes.
  def MatchPrefix(lab, prefixes):
    for prefix_dash in prefixes:
      if lab.lower().startswith(prefix_dash):
        return prefix_dash
    return False

  # Dedup any added labels.  E.g., ignore attempts to add Priority twice.
  excl_add = []
  dedupped_labels_add = []
  for lab in labels_add:
    matched_prefix_dash = MatchPrefix(lab, exclusive_prefixes)
    if matched_prefix_dash:
      if matched_prefix_dash not in excl_add:
        excl_add.append(matched_prefix_dash)
        dedupped_labels_add.append(lab)
    else:
      dedupped_labels_add.append(lab)

  # "Old minus exclusive" is the set of old label values minus any
  # that should be overwritten by newly set exclusive labels.
  old_minus_excl = []
  for lab in labels_list:
    matched_prefix_dash = MatchPrefix(lab, excl_add)
    if not matched_prefix_dash:
      old_minus_excl.append(lab)

  merged_labels = [lab for lab in old_minus_excl + dedupped_labels_add
                   if lab.lower() not in labels_remove_lower]

  return merged_labels, dedupped_labels_add, labels_remove


# Pattern to match a valid hotlist name.
RE_HOTLIST_NAME_PATTERN = r"[a-zA-Z][-0-9a-zA-Z\.]*"

# Compiled regexp to match the hotlist name and nothing more before or after.
RE_HOTLIST_NAME = re.compile(
    '^%s$' % RE_HOTLIST_NAME_PATTERN, re.VERBOSE)


def IsValidHotlistName(s):
  """Return true if the given string is a valid hotlist name."""
  return (RE_HOTLIST_NAME.match(s) and
          len(s) <= framework_constants.MAX_HOTLIST_NAME_LENGTH)


USER_PREF_DEFS = {
  'code_font': re.compile('(true|false)'),

  # The are for dismissible cues.  True means the user has dismissed them.
  'privacy_click_through': re.compile('(true|false)'),
  'corp_mode_click_through': re.compile('(true|false)'),
  'code_of_conduct': re.compile('(true|false)'),
  'dit_keystrokes': re.compile('(true|false)'),
  'italics_mean_derived': re.compile('(true|false)'),
  'availability_msgs': re.compile('(true|false)'),
  'your_email_bounced': re.compile('(true|false)'),
  'search_for_numbers': re.compile('(true|false)'),
  'restrict_new_issues': re.compile('(true|false)'),
  'public_issue_notice': re.compile('(true|false)'),
  'you_are_on_vacation': re.compile('(true|false)'),
  'how_to_join_project': re.compile('(true|false)'),
  'document_team_duties': re.compile('(true|false)'),
  'showing_ids_instead_of_tiles': re.compile('(true|false)'),
  'issue_timestamps': re.compile('(true|false)'),
  'stale_fulltext': re.compile('(true|false)'),
  }
MAX_PREF_VALUE_LENGTH = 80


def ValidatePref(name, value):
  """Return an error message if the server does not support a pref value."""
  if name not in USER_PREF_DEFS:
    return 'Unknown pref name: %r' % name
  if len(value) > MAX_PREF_VALUE_LENGTH:
    return 'Value for pref name %r is too long' % name
  if not USER_PREF_DEFS[name].match(value):
    return 'Invalid pref value %r for %r' % (value, name)
  return None


def IsCorpUser(cnxn, services, user_id):
  """Return true if user should get a UX similar to corp systems."""
  user_group_ids = services.usergroup.LookupMemberships(cnxn, user_id)
  corp_mode_groups_dict = services.user.LookupUserIDs(
      cnxn, settings.corp_mode_user_groups, autocreate=True)
  corp_mode_group_ids = set(corp_mode_groups_dict.values())
  corp_mode = any(gid in corp_mode_group_ids for gid in user_group_ids)
  return corp_mode
