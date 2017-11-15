# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for custom field sevlets."""

import collections
import logging
import re

from framework import authdata
from framework import framework_bizobj
from framework import framework_constants
from framework import permissions
from framework import timestr
from proto import tracker_pb2
from services import config_svc
from services import user_svc
from tracker import tracker_bizobj


INVALID_USER_ID = -1

ParsedFieldDef = collections.namedtuple(
    'ParsedFieldDef',
    'field_name, field_type_str, min_value, max_value, regex, '
    'needs_member, needs_perm, grants_perm, notify_on, is_required, '
    'is_niche, importance, is_multivalued, field_docstring, choices_text, '
    'applicable_type, applicable_predicate, revised_labels, date_action_str')


def ParseFieldDefRequest(post_data, config):
  """Parse the user's HTML form data to update a field definition."""
  field_name = post_data.get('name', '')
  field_type_str = post_data.get('field_type')
  # TODO(jrobbins): once a min or max is set, it cannot be completely removed.
  min_value_str = post_data.get('min_value')
  try:
    min_value = int(min_value_str)
  except (ValueError, TypeError):
    min_value = None
  max_value_str = post_data.get('max_value')
  try:
    max_value = int(max_value_str)
  except (ValueError, TypeError):
    max_value = None
  regex = post_data.get('regex')
  needs_member = 'needs_member' in post_data
  needs_perm = post_data.get('needs_perm', '').strip()
  grants_perm = post_data.get('grants_perm', '').strip()
  notify_on_str = post_data.get('notify_on')
  if notify_on_str in config_svc.NOTIFY_ON_ENUM:
    notify_on = config_svc.NOTIFY_ON_ENUM.index(notify_on_str)
  else:
    notify_on = 0
  importance = post_data.get('importance')
  is_required = (importance == 'required')
  is_niche = (importance == 'niche')
  is_multivalued = 'is_multivalued' in post_data
  field_docstring = post_data.get('docstring', '')
  choices_text = post_data.get('choices', '')
  applicable_type = post_data.get('applicable_type', '')
  applicable_predicate = ''  # TODO(jrobbins): placeholder for future feature
  revised_labels = _ParseChoicesIntoWellKnownLabels(
      choices_text, field_name, config)
  date_action_str = post_data.get('date_action')

  return ParsedFieldDef(
      field_name, field_type_str, min_value, max_value, regex,
      needs_member, needs_perm, grants_perm, notify_on, is_required, is_niche,
      importance, is_multivalued, field_docstring, choices_text,
      applicable_type, applicable_predicate, revised_labels, date_action_str)


def _ParseChoicesIntoWellKnownLabels(choices_text, field_name, config):
  """Parse a field's possible choices and integrate them into the config.

  Args:
    choices_text: string with one label and optional docstring per line.
    field_name: string name of the field definition being edited.
    config: ProjectIssueConfig PB of the current project.

  Returns:
    A revised list of labels that can be used to update the config.
  """
  matches = framework_constants.IDENTIFIER_DOCSTRING_RE.findall(choices_text)
  new_labels = [
      ('%s-%s' % (field_name, label), choice_docstring.strip(), False)
      for label, choice_docstring in matches]
  kept_labels = [
      (wkl.label, wkl.label_docstring, False)
      for wkl in config.well_known_labels
      if not tracker_bizobj.LabelIsMaskedByField(
          wkl.label, [field_name.lower()])]
  revised_labels = kept_labels + new_labels
  return revised_labels


def ShiftEnumFieldsIntoLabels(
    labels, labels_remove, field_val_strs, field_val_strs_remove, config):
  """Look at the custom field values and treat enum fields as labels.

  Args:
    labels: list of labels to add/set on the issue.
    labels_remove: list of labels to remove from the issue.
    field_val_strs: {field_id: [val_str, ...]} of custom fields to add/set.
    field_val_strs_remove: {field_id: [val_str, ...]} of custom fields to
        remove.
    config: ProjectIssueConfig PB including custom field definitions.

  SIDE-EFFECT: the labels and labels_remove lists will be extended with
  key-value labels corresponding to the enum field values.  Those field
  entries will be removed from field_vals and field_vals_remove.
  """
  for fd in config.field_defs:
    if fd.field_type != tracker_pb2.FieldTypes.ENUM_TYPE:
      continue

    if fd.field_id in field_val_strs:
      labels.extend(
          '%s-%s' % (fd.field_name, val)
          for val in field_val_strs[fd.field_id]
          if val and val != '--')
      del field_val_strs[fd.field_id]

    if fd.field_id in field_val_strs_remove:
      labels_remove.extend(
          '%s-%s' % (fd.field_name, val)
          for val in field_val_strs_remove[fd.field_id]
          if val and val != '--')
      del field_val_strs_remove[fd.field_id]


def _ParseOneFieldValue(cnxn, user_service, fd, val_str):
  """Make one FieldValue PB from the given user-supplied string."""
  if fd.field_type == tracker_pb2.FieldTypes.INT_TYPE:
    try:
      return tracker_bizobj.MakeFieldValue(
          fd.field_id, int(val_str), None, None, None, None, False)
    except ValueError:
      return None  # TODO(jrobbins): should bounce

  elif fd.field_type == tracker_pb2.FieldTypes.STR_TYPE:
    return tracker_bizobj.MakeFieldValue(
        fd.field_id, None, val_str, None, None, None, False)

  elif fd.field_type == tracker_pb2.FieldTypes.USER_TYPE:
    if val_str:
      try:
        user_id = user_service.LookupUserID(cnxn, val_str, autocreate=False)
      except user_svc.NoSuchUserException:
        # Set to invalid user ID to display error during the validation step.
        user_id = INVALID_USER_ID
      return tracker_bizobj.MakeFieldValue(
          fd.field_id, None, None, user_id, None, None, False)
    else:
      return None

  if fd.field_type == tracker_pb2.FieldTypes.DATE_TYPE:
    try:
      timestamp = timestr.DateWidgetStrToTimestamp(val_str)
      return tracker_bizobj.MakeFieldValue(
          fd.field_id, None, None, None, timestamp, None, False)
    except ValueError:
      return None  # TODO(jrobbins): should bounce

  if fd.field_type == tracker_pb2.FieldTypes.URL_TYPE:
    try:
      return tracker_bizobj.MakeFieldValue(
          fd.field_id, None, None, None, None, val_str, False)
    except ValueError:
      return None # TODO(jojwang): should bounce

  else:
    logging.error('Cant parse field with unexpected type %r', fd.field_type)
    return None


def ParseFieldValues(cnxn, user_service, field_val_strs, config):
  """Return a list of FieldValue PBs based on the given dict of strings."""
  field_values = []
  for fd in config.field_defs:
    if fd.field_id not in field_val_strs:
      continue
    for val_str in field_val_strs[fd.field_id]:
      fv = _ParseOneFieldValue(cnxn, user_service, fd, val_str)
      if fv:
        field_values.append(fv)

  return field_values


def _ValidateOneCustomField(mr, services, field_def, field_val):
  """Validate one custom field value and return an error string or None."""
  if field_def.field_type == tracker_pb2.FieldTypes.INT_TYPE:
    if (field_def.min_value is not None and
        field_val.int_value < field_def.min_value):
      return 'Value must be >= %d' % field_def.min_value
    if (field_def.max_value is not None and
        field_val.int_value > field_def.max_value):
      return 'Value must be <= %d' % field_def.max_value

  elif field_def.field_type == tracker_pb2.FieldTypes.STR_TYPE:
    if field_def.regex and field_val.str_value:
      try:
        regex = re.compile(field_def.regex)
        if not regex.match(field_val.str_value):
          return 'Value must match regular expression: %s' % field_def.regex
      except re.error:
        logging.info('Failed to process regex %r with value %r. Allowing.',
                     field_def.regex, field_val.str_value)
        return None

  elif field_def.field_type == tracker_pb2.FieldTypes.USER_TYPE:
    if field_val.user_id == INVALID_USER_ID:
      return 'User not found'
    if field_def.needs_member:
      auth = authdata.AuthData.FromUserID(
          mr.cnxn, field_val.user_id, services)
      user_value_in_project = framework_bizobj.UserIsInProject(
          mr.project, auth.effective_ids)
      if not user_value_in_project:
        return 'User must be a member of the project'
      if field_def.needs_perm:
        field_val_user = services.user.GetUser(mr.cnxn, field_val.user_id)
        user_perms = permissions.GetPermissions(
            field_val_user, auth.effective_ids, mr.project)
        has_perm = user_perms.CanUsePerm(
            field_def.needs_perm, auth.effective_ids, mr.project, [])
        if not has_perm:
          return 'User must have permission "%s"' % field_def.needs_perm

  elif field_def.field_type == tracker_pb2.FieldTypes.DATE_TYPE:
    # TODO(jrobbins): date validation
    pass

  elif field_def.field_type == tracker_pb2.FieldTypes.URL_TYPE:
    # TODO(jojwang): url validation, this blocks feature launch.
    pass

  return None


def ValidateCustomFields(mr, services, field_values, config, errors):
  """Validate each of the given fields and report problems in errors object."""
  for fv in field_values:
    fd = tracker_bizobj.FindFieldDefByID(fv.field_id, config)
    if fd:
      err_msg = _ValidateOneCustomField(mr, services, fd, fv)
      if err_msg:
        errors.SetCustomFieldError(fv.field_id, err_msg)
