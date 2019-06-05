# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A servlet for project and component owners to view and edit field defs."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import time
import re

from third_party import ezt

from framework import exceptions
from framework import framework_helpers
from framework import framework_views
from framework import permissions
from framework import servlet
from framework import urls
from proto import tracker_pb2
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from tracker import tracker_views


class FieldDetail(servlet.Servlet):
  """Servlet allowing project owners to view and edit a custom field."""

  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS
  _PAGE_TEMPLATE = 'tracker/field-detail-page.ezt'

  def _GetFieldDef(self, mr):
    """Get the config and field definition to be viewed or edited."""
    # TODO(jrobbins): since so many requests get the config object, and
    # it is usually cached in RAM, just always get it and include it
    # in the MonorailRequest, mr.
    config = self.services.config.GetProjectConfig(
        mr.cnxn, mr.project_id, use_cache=False)
    field_def = tracker_bizobj.FindFieldDef(mr.field_name, config)
    if not field_def:
      self.abort(404, 'custom field not found')
    return config, field_def

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(FieldDetail, self).AssertBasePermission(mr)
    _config, field_def = self._GetFieldDef(mr)

    allow_view = permissions.CanViewFieldDef(
        mr.auth.effective_ids, mr.perms, mr.project, field_def)
    if not allow_view:
      raise permissions.PermissionException(
          'User is not allowed to view this field definition')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    config, field_def = self._GetFieldDef(mr)
    approval_def, subfields = None, []
    if field_def.field_type == tracker_pb2.FieldTypes.APPROVAL_TYPE:
      approval_def = tracker_bizobj.FindApprovalDefByID(
          field_def.field_id, config)
      user_views = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, field_def.admin_ids,
          approval_def.approver_ids)
      subfields = tracker_bizobj.FindApprovalsSubfields(
          [field_def.field_id], config)[field_def.field_id]
    else:
      user_views = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, field_def.admin_ids)
    field_def_view = tracker_views.FieldDefView(
        field_def, config, user_views=user_views, approval_def=approval_def)

    well_known_issue_types = tracker_helpers.FilterIssueTypes(config)

    allow_edit = permissions.CanEditFieldDef(
        mr.auth.effective_ids, mr.perms, mr.project, field_def)

    # Right now we do not allow renaming of enum fields.
    _uneditable_name = field_def.field_type == tracker_pb2.FieldTypes.ENUM_TYPE

    initial_choices = '\n'.join(
        [choice.name if not choice.docstring else (
            choice.name + ' = ' + choice.docstring) for
         choice in field_def_view.choices])

    initial_approvers = ', '.join(sorted([
      approver_view.email for approver_view in field_def_view.approvers]))

    initial_admins = ', '.join(sorted([
        uv.email for uv in field_def_view.admins]))

    return {
        'admin_tab_mode': servlet.Servlet.PROCESS_TAB_LABELS,
        'field_def': field_def_view,
        'allow_edit': ezt.boolean(allow_edit),
        # TODO(jojwang): update when name changes are actually saved
        'uneditable_name': ezt.boolean(True),
        'initial_admins': initial_admins,
        'initial_applicable_type': field_def.applicable_type,
        'initial_applicable_predicate': field_def.applicable_predicate,
        'initial_approvers': initial_approvers,
        'initial_choices': initial_choices,
        'approval_subfields': [fd for fd in subfields if not fd.is_deleted],
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
    config, field_def = self._GetFieldDef(mr)
    allow_edit = permissions.CanEditFieldDef(
        mr.auth.effective_ids, mr.perms, mr.project, field_def)
    if not allow_edit:
      raise permissions.PermissionException(
          'User is not allowed to delete this field')

    if 'deletefield' in post_data:
      return self._ProcessDeleteField(mr, config, field_def)
    elif 'cancel' in post_data:
      return framework_helpers.FormatAbsoluteURL(
          mr, urls.ADMIN_LABELS, ts=int(time.time()))
    else:
      return self._ProcessEditField(mr, post_data, config, field_def)


  def _ProcessDeleteField(self, mr, config, field_def):
    """The user wants to delete the specified custom field definition."""
    field_ids = [field_def.field_id]
    if field_def.field_type is tracker_pb2.FieldTypes.APPROVAL_TYPE:
      for fd in config.field_defs:
        if fd.approval_id == field_def.field_id:
          field_ids.append(fd.field_id)
    self.services.config.SoftDeleteFieldDefs(
        mr.cnxn, mr.project_id, field_ids)

    return framework_helpers.FormatAbsoluteURL(
          mr, urls.ADMIN_LABELS, deleted=1, ts=int(time.time()))

    # TODO(jrobbins): add logic to reaper cron task to look for
    # soft deleted field definitions that have no issues with
    # any value and hard deleted them.

  def _ProcessEditField(self, mr, post_data, config, field_def):
    """The user wants to edit this field definition."""
    # TODO(jrobbins): future feature: editable field names

    parsed = field_helpers.ParseFieldDefRequest(post_data, config)

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

    if field_def.field_type == tracker_pb2.FieldTypes.APPROVAL_TYPE:
      if parsed.approvers_str:
        approver_ids_dict = self.services.user.LookupUserIDs(
            mr.cnxn, re.split('[,;\s]+', parsed.approvers_str),
            autocreate=True)
        approver_ids = list(set(approver_ids_dict.values()))
      else:
        mr.errors.approvers = 'Please provide at least one default approver.'

    if mr.errors.AnyErrors():
      new_field_def = field_helpers.ReviseFieldDefFromParsed(parsed, field_def)

      new_field_def_view = tracker_views.FieldDefView(
          new_field_def, config)

      self.PleaseCorrect(
          mr, field_def=new_field_def_view,
          initial_applicable_type=parsed.applicable_type,
          initial_choices=parsed.choices_text,
          initial_admins = admin_str,
          initial_approvers = parsed.approvers_str)
      return

    self.services.config.UpdateFieldDef(
        mr.cnxn, mr.project_id, field_def.field_id,
        applicable_type=parsed.applicable_type,
        applicable_predicate=parsed.applicable_predicate,
        is_required=parsed.is_required, is_niche=parsed.is_niche,
        min_value=parsed.min_value, max_value=parsed.max_value,
        regex=parsed.regex, needs_member=parsed.needs_member,
        needs_perm=parsed.needs_perm, grants_perm=parsed.grants_perm,
        notify_on=parsed.notify_on, is_multivalued=parsed.is_multivalued,
        date_action=parsed.date_action_str,
        docstring=parsed.field_docstring, admin_ids=admin_ids)

    if field_def.field_type == tracker_pb2.FieldTypes.APPROVAL_TYPE:
      approval_defs = field_helpers.ReviseApprovals(
          field_def.field_id, approver_ids, parsed.survey, config)
      self.services.config.UpdateConfig(
          mr.cnxn, mr.project, approval_defs=approval_defs)

    if field_def.field_type == tracker_pb2.FieldTypes.ENUM_TYPE:
      self.services.config.UpdateConfig(
          mr.cnxn, mr.project, well_known_labels=parsed.revised_labels)

    return framework_helpers.FormatAbsoluteURL(
          mr, urls.FIELD_DETAIL, field=field_def.field_name,
          saved=1, ts=int(time.time()))
