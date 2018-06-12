# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A servlet for project owners to edit/delete a template"""

import collections
import logging
import time

from third_party import ezt

from framework import authdata
from framework import framework_bizobj
from framework import framework_helpers
from framework import framework_views
from framework import servlet
from framework import urls
from framework import permissions
from tracker import field_helpers
from tracker import template_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from tracker import tracker_views
from proto import tracker_pb2
from services import user_svc


class TemplateDetail(servlet.Servlet):
  """Servlet allowing project owners to edit/delete an issue template"""

  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS
  _PAGE_TEMPLATE = 'tracker/template-detail-page.ezt'
  _PROCESS_SUBTAB = servlet.Servlet.PROCESS_TAB_TEMPLATES

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(TemplateDetail, self).AssertBasePermission(mr)
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    template_set = self.services.template.GetProjectTemplates(mr.cnxn,
        config.project_id)
    template = tracker_bizobj.FindIssueTemplate(mr.template_name,
        template_set.templates)

    if template:
      allow_view = permissions.CanViewTemplate(
          mr.auth.effective_ids, mr.perms, mr.project, template)
      if not allow_view:
        raise permissions.PermissionException(
            'User is not allowed to view this issue template')
    else:
      self.abort(404, 'issue template not found %s' % mr.template_name)

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    template_set = self.services.template.GetProjectTemplates(mr.cnxn,
        config.project_id)
    template = tracker_bizobj.FindIssueTemplate(mr.template_name,
        template_set.templates)
    template_view = tracker_views.IssueTemplateView(
        mr, template, self.services.user, config)
    with mr.profiler.Phase('making user views'):
      users_involved = tracker_bizobj.UsersInvolvedInTemplate(template)
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mr.auth, mr.project, users_by_id)
    field_name_set = {fd.field_name.lower() for fd in config.field_defs
                      if not fd.is_deleted}
    non_masked_labels = tracker_bizobj.NonMaskedLabels(
        template.labels, field_name_set)

    field_views = tracker_views.MakeAllFieldValueViews(
      config, template.labels, [], template.field_values, users_by_id)
    approval_subfields_present = False
    if any(fv.field_def.is_approval_subfield for fv in field_views):
      approval_subfields_present = True

    (prechecked_approvals, required_approval_ids,
     initial_phases) = template_helpers.GatherApprovalsPageData(
         template.approval_values, template.phases)

    allow_edit = permissions.CanEditTemplate(
        mr.auth.effective_ids, mr.perms, mr.project, template)

    return {
        'admin_tab_mode': self._PROCESS_SUBTAB,
        'allow_edit': ezt.boolean(allow_edit),
        'new_template_form': ezt.boolean(False),
        'initial_members_only': template_view.members_only,
        'template_name': template_view.name,
        'initial_summary': template_view.summary,
        'initial_must_edit_summary': template_view.summary_must_be_edited,
        'initial_content': template_view.content,
        'initial_status': template_view.status,
        'initial_owner': template_view.ownername,
        'initial_owner_defaults_to_member':
        template_view.owner_defaults_to_member,
        'initial_components': template_view.components,
        'initial_component_required': template_view.component_required,
        'fields': [view for view in field_views
                   if view.field_def.type_name is not 'APPROVAL_TYPE'],
        'initial_add_phases': ezt.boolean(template.phases),
        'initial_phases': initial_phases,
        'approvals': [view for view in field_views
                      if view.field_def.type_name is 'APPROVAL_TYPE'],
        'prechecked_approvals': prechecked_approvals,
        'required_approval_ids': required_approval_ids,
        'labels': non_masked_labels,
        'initial_admins': template_view.admin_names,
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
    parsed = template_helpers.ParseTemplateRequest(post_data, config)
    field_helpers.ShiftEnumFieldsIntoLabels(
        parsed.labels, [], parsed.field_val_strs, [], config)
    template_set = self.services.template.GetProjectTemplates(mr.cnxn,
        config.project_id)
    template = tracker_bizobj.FindIssueTemplate(parsed.name,
        template_set.templates)
    allow_edit = permissions.CanEditTemplate(
        mr.auth.effective_ids, mr.perms, mr.project, template)
    if not allow_edit:
      raise permissions.PermissionException(
          'User is not allowed edit this issue template.')

    if 'deletetemplate' in post_data:
      self.services.template.DeleteIssueTemplateDef(
          mr.cnxn, mr.project_id, template.template_id)
      return framework_helpers.FormatAbsoluteURL(
          mr, urls.ADMIN_TEMPLATES, deleted=1, ts=int(time.time()))

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
          initial_summary=parsed.summary,
          initial_must_edit_summary=ezt.boolean(parsed.summary_must_be_edited),
          initial_content=parsed.content,
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
    self.services.template.UpdateIssueTemplateDef(
        mr.cnxn, mr.project_id, template.template_id, name=parsed.name,
        content=parsed.content, summary=parsed.summary,
        summary_must_be_edited=parsed.summary_must_be_edited,
        status=parsed.status, members_only=parsed.members_only,
        owner_defaults_to_member=parsed.owner_defaults_to_member,
        component_required=parsed.component_required, owner_id=owner_id,
        labels=labels, component_ids=component_ids, admin_ids=admin_ids,
        field_values=field_values, phases=phases, approval_values=approvals)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.TEMPLATE_DETAIL, template=template.name,
        saved=1, ts=int(time.time()))
