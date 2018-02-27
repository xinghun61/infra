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
from framework import servlet
from framework import urls
from framework import permissions
from tracker import field_helpers
from tracker import template_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from tracker import tracker_views
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

    template = tracker_bizobj.FindIssueTemplate(mr.template_name, config)

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
    template = tracker_bizobj.FindIssueTemplate(mr.template_name, config)
    template_view = tracker_views.IssueTemplateView(
        mr, template, self.services.user, config)
    fd_id_to_fvs = collections.defaultdict(list)
    for fv in template.field_values:
      fd_id_to_fvs[fv.field_id].append(fv)

    field_views = [
      tracker_views.MakeFieldValueView(fd, config, [], [],
                                       fd_id_to_fvs[fd.field_id], {})
      for fd in config.field_defs if not fd.is_deleted]

    allow_edit = permissions.CanEditTemplate(
        mr.auth.effective_ids, mr.perms, mr.project, template)

    return {
        'admin_tab_mode': self._PROCESS_SUBTAB,
        'allow_edit': ezt.boolean(allow_edit),
        'new_template_form': ezt.boolean(False),
        'template': template_view,
        'fields': field_views,
        'labels': template.labels,
        'initial_owner': template_view.ownername,
        'initial_components': template_view.components,
        'initial_admins': template_view.admin_names,
        }

def ProcessFormData(_self, mr, _post_data):
    """Validate and store the contents of the issues tracker admin page.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """
    # TODO(jojwang): Parse post_data and save template

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.TEMPLATE_DETAIL)
