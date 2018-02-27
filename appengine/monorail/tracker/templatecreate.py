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
    field_views = [
      tracker_views.MakeFieldValueView(fd, config, [], [], [], {})
      for fd in config.field_defs if not fd.is_deleted]
    return {
        'admin_tab_mode': self._PROCESS_SUBTAB,
        'allow_edit': ezt.boolean(True),
        'new_template_form': ezt.boolean(True),
        'initial_members_only': ezt.boolean(False),
        'template_name': '',
        'initial_content': '',
        'initial_must_edit_summary': ezt.boolean(False),
        'initial_description': '',
        'initial_status': '',
        'initial_owner': '',
        'initial_owner_defaults_to_member': ezt.boolean(False),
        'initial_components': '',
        'initial_component_required': ezt.boolean(False),
        'initial_admins': '',
        'fields': field_views,
        }

  def ProcessFormData(self, mr, post_data):
    """Validate and store the contents of the issues tracker admin page.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """

    admin_ids, admin_str = tracker_helpers.ParseAdminUsers(
        mr.cnxn, post_data.get('admin_names', ''), self.services.user)

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    parsed = template_helpers.ParseTemplateRequest(post_data, config)

    owner_id = 0
    if parsed.owner_str:
      try:
        user_id = self.services.user.LookupUserID(mr.cnxn, parsed.owner_str)
        auth = authdata.AuthData.FromUserID(mr.cnxn, user_id, self.services)
        if framework_bizobj.UserIsInProject(mr.project, auth.effective_ids):
          owner_id = user_id
        else:
          mr.errors.owner = 'User is not a member of this project.'
      except user_svc.NoSuchUserException:
        mr.errors.owner = 'Owner not found.'

    component_ids = tracker_helpers.LookupComponentIDs(
        parsed.component_paths, config, mr.errors)

    field_values = field_helpers.ParseFieldValues(
        mr.cnxn, self.services.user, parsed.field_val_strs, config)
    for fv in field_values:
      logging.info('field_value is %r: %r',
                   fv.field_id, tracker_bizobj.GetFieldValue(fv, {}))

    if mr.errors.AnyErrors():
      fd_id_to_fvs = collections.defaultdict(list)
      for fv in field_values:
        fd_id_to_fvs[fv.field_id].append(fv)

      field_views = [
          tracker_views.MakeFieldValueView(fd, config, [], [],
                                           fd_id_to_fvs[fd.field_id], {})
          for fd in config.field_defs if not fd.is_deleted]

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
          initial_admins=admin_str,
          labels=parsed.labels,
          fields=field_views
      )
      return

    templates = config.templates
    templates.append(tracker_bizobj.MakeIssueTemplate(
        parsed.name, parsed.summary, parsed.status, owner_id, parsed.content,
        parsed.labels, field_values, admin_ids, component_ids,
        summary_must_be_edited=parsed.summary_must_be_edited,
        owner_defaults_to_member=parsed.owner_defaults_to_member,
        component_required=parsed.component_required,
        members_only=parsed.members_only
    ))

    # TODO(jojwang): monorail:3537, implement services.config.CreateTemplate()

    self.services.config.UpdateConfig(
        mr.cnxn, mr.project, templates=templates)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ADMIN_TEMPLATES, saved=1, ts=int(time.time()))
