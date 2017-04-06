# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A servlet for project owners to create a new field def."""

import logging
import re
import time

from third_party import ezt

from framework import framework_helpers
from framework import jsonfeed
from framework import permissions
from framework import servlet
from framework import urls
from tracker import field_helpers
from tracker import tracker_constants
from tracker import tracker_helpers


class FieldCreate(servlet.Servlet):
  """Servlet allowing project owners to create a custom field."""

  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS
  _PAGE_TEMPLATE = 'tracker/field-create-page.ezt'

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(FieldCreate, self).AssertBasePermission(mr)
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'You are not allowed to administer this project')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    well_known_issue_types = tracker_helpers.FilterIssueTypes(config)

    return {
        'admin_tab_mode': servlet.Servlet.PROCESS_TAB_LABELS,
        'initial_field_name': '',
        'initial_field_docstring': '',
        'initial_importance': 'normal',
        'initial_is_multivalued': ezt.boolean(False),
        'initial_choices': '',
        'initial_admins': '',
        'initial_type': 'enum_type',
        'initial_applicable_type': '',  # That means any issue type
        'initial_applicable_predicate': '',
        'initial_needs_member': ezt.boolean(False),
        'initial_needs_perm': '',
        'initial_grants_perm': '',
        'initial_notify_on': 0,
        'initial_date_action': 'no_action',
        'well_known_issue_types': well_known_issue_types,
        }

  def ProcessFormData(self, mr, post_data):
    """Validate and store the contents of the issues tracker admin page.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    parsed = field_helpers.ParseFieldDefRequest(post_data, config)

    if not tracker_constants.FIELD_NAME_RE.match(parsed.field_name):
      mr.errors.field_name = 'Invalid field name'

    field_name_error_msg = FieldNameErrorMessage(parsed.field_name, config)
    if field_name_error_msg:
      mr.errors.field_name = field_name_error_msg

    if (parsed.min_value is not None and parsed.max_value is not None and
        parsed.min_value > parsed.max_value):
      mr.errors.min_value = 'Minimum value must be less than maximum.'

    if parsed.regex:
      try:
        re.compile(parsed.regex)
      except re.error:
        mr.errors.regex = 'Invalid regular expression.'

    admin_ids, admin_str = tracker_helpers.ParseAdminUsers(
        mr.cnxn, post_data['admin_names'], self.services.user)

    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, initial_field_name=parsed.field_name,
          initial_type=parsed.field_type_str,
          initial_field_docstring=parsed.field_docstring,
          initial_applicable_type=parsed.applicable_type,
          initial_applicable_predicate=parsed.applicable_predicate,
          initial_needs_member=ezt.boolean(parsed.needs_member),
          initial_needs_perm=parsed.needs_perm,
          initial_importance=parsed.importance,
          initial_is_multivalued=ezt.boolean(parsed.is_multivalued),
          initial_grants_perm=parsed.grants_perm,
          initial_notify_on=parsed.notify_on,
          initial_date_action=parsed.date_action_str,
          initial_choices=parsed.choices_text,
          initial_admins=admin_str)
      return

    print 'parsed is %r' % (parsed,)
    self.services.config.CreateFieldDef(
        mr.cnxn, mr.project_id, parsed.field_name, parsed.field_type_str,
        parsed.applicable_type, parsed.applicable_predicate,
        parsed.is_required, parsed.is_niche, parsed.is_multivalued,
        parsed.min_value, parsed.max_value, parsed.regex, parsed.needs_member,
        parsed.needs_perm, parsed.grants_perm, parsed.notify_on,
        parsed.date_action_str, parsed.field_docstring, admin_ids)
    if parsed.field_type_str == 'enum_type':
      self.services.config.UpdateConfig(
          mr.cnxn, mr.project, well_known_labels=parsed.revised_labels)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ADMIN_LABELS, saved=1, ts=int(time.time()))


class CheckFieldNameJSON(jsonfeed.JsonFeed):
  """JSON data for handling name checks when creating a field."""

  def HandleRequest(self, mr):
    """Provide the UI with info about the availability of the field name.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format.
    """
    field_name = mr.GetParam('field')
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    choices = ExistingEnumChoices(field_name, config)
    choices_dicts = [dict(name=choice.name_padded, doc=choice.docstring)
                     for choice in choices]
    message = FieldNameErrorMessage(field_name, config)

    return {
        'error_message': message,
        'choices': choices_dicts,
        }


def FieldNameErrorMessage(field_name, config):
  """Return an error message for the given field name, or None."""
  field_name_lower = field_name.lower()
  if field_name_lower in tracker_constants.RESERVED_PREFIXES:
    return 'That name is reserved.'

  for fd in config.field_defs:
    fn_lower = fd.field_name.lower()
    if field_name_lower == fn_lower:
      return 'That name is already in use.'
    if field_name_lower.startswith(fn_lower + '-'):
      return 'An existing field name is a prefix of that name.'
    if fn_lower.startswith(field_name_lower + '-'):
      return 'That name is a prefix of an existing field name.'

  return None


def ExistingEnumChoices(field_name, config):
  """Return a list of existing label choices for the given prefix."""
  # If there are existing labels with that prefix, then it must be enum.
  # The existing labels will be treated as field values.
  choices = tracker_helpers.LabelsMaskedByFields(
      config, [field_name], trim_prefix=True)
  return choices
