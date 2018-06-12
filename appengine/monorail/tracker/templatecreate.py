# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A servlet for project owners to create a new template"""

import collections
import logging
import time

from third_party import ezt

from framework import authdata
from framework import framework_bizobj
from framework import framework_helpers
from framework import servlet
from framework import urls
from framework import permissions
from tracker import field_helpers
from tracker import template_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from tracker import tracker_views
from services import user_svc
from proto import tracker_pb2


class TemplateCreate(servlet.Servlet):
  """Servlet allowing project owners to create an issue template."""

  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS
  _PAGE_TEMPLATE = 'tracker/template-detail-page.ezt'
  _PROCESS_SUBTAB = servlet.Servlet.PROCESS_TAB_TEMPLATES

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request
    """
    super(TemplateCreate, self).AssertBasePermission(mr)
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'User is not allowed to administer this project')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    field_views = tracker_views.MakeAllFieldValueViews(
        config, [], [], [], {})
    approval_subfields_present = False
    if any(fv.field_def.is_approval_subfield for fv in field_views):
      approval_subfields_present = True

    initial_phases = [tracker_pb2.Phase()] * template_helpers.MAX_NUM_PHASES
    return {
        'admin_tab_mode': self._PROCESS_SUBTAB,
        'allow_edit': ezt.boolean(True),
        'new_template_form': ezt.boolean(True),
        'initial_members_only': ezt.boolean(False),
        'template_name': '',
        'initial_content': '',
        'initial_must_edit_summary': ezt.boolean(False),
        'initial_summary': '',
        'initial_status': '',
        'initial_owner': '',
        'initial_owner_defaults_to_member': ezt.boolean(False),
        'initial_components': '',
        'initial_component_required': ezt.boolean(False),
        'initial_admins': '',
        'fields': [view for view in field_views
                   if view.field_def.type_name is not "APPROVAL_TYPE"],
        'initial_add_phases': ezt.boolean(False),
        'initial_phases': initial_phases,
        'approvals': [view for view in field_views
                   if view.field_def.type_name is "APPROVAL_TYPE"],
        'prechecked_approvals': [],
        'required_approval_ids': [],
        'approval_subfields_present': ezt.boolean(approval_subfields_present),
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
    template_set = self.services.template.GetProjectTemplates(mr.cnxn,
        config.project_id)
    parsed = template_helpers.ParseTemplateRequest(post_data, config)
    field_helpers.ShiftEnumFieldsIntoLabels(
        parsed.labels, [], parsed.field_val_strs, [], config)

    if not parsed.name:
      mr.errors.name = 'Please provide a template name'
    if tracker_bizobj.FindIssueTemplate(parsed.name, template_set.templates):
      mr.errors.name = 'Template with name %s already exists' % parsed.name

    (admin_ids, owner_id, component_ids,
     field_values, phases,
     approvals) = template_helpers.GetTemplateInfoFromParsed(
         mr, self.services, parsed, config)

    if mr.errors.AnyErrors():
      field_views = tracker_views.MakeAllFieldValueViews(
          config, [], [], field_values, {})
      prechecked_approvals = template_helpers.GetCheckedApprovalsFromParsed(
          parsed.approvals_to_phase_idx)

      self.PleaseCorrect(
          mr,
          initial_members_only=ezt.boolean(parsed.members_only),
          template_name=parsed.name,
          initial_content=parsed.summary,
          initial_must_edit_summary=ezt.boolean(parsed.summary_must_be_edited),
          initial_description=parsed.content,
          initial_status=parsed.status,
          initial_owner=parsed.owner_str,
          initial_owner_defaults_to_member=ezt.boolean(
              parsed.owner_defaults_to_member),
          initial_components=', '.join(parsed.component_paths),
          initial_component_required=ezt.boolean(parsed.component_required),
          initial_admins=parsed.admin_str,
          labels=parsed.labels,
          fields=[view for view in field_views
                  if view.field_def.type_name is not 'APPROVAL_TYPE'],
          initial_add_phases=ezt.boolean(parsed.add_phases),
          initial_phases=[tracker_pb2.Phase(name=name) for name in
                          parsed.phase_names],
          approvals=[view for view in field_views
                     if view.field_def.type_name is 'APPROVAL_TYPE'],
          prechecked_approvals=prechecked_approvals,
          required_approval_ids=parsed.required_approval_ids
      )
      return

    labels = [label for label in parsed.labels if label]
    self.services.template.CreateIssueTemplateDef(
        mr.cnxn, mr.project_id, parsed.name, parsed.content, parsed.summary,
        parsed.summary_must_be_edited, parsed.status, parsed.members_only,
        parsed.owner_defaults_to_member, parsed.component_required,
        owner_id, labels, component_ids, admin_ids, field_values, phases=phases,
        approval_values=approvals)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ADMIN_TEMPLATES, saved=1, ts=int(time.time()))
