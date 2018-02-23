# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A servlet for project owners to create a new template"""

import logging

from third_party import ezt

from framework import servlet
from framework import urls
from framework import permissions
from tracker import tracker_views


class TemplateCreate(servlet.Servlet):
  """Servlet allowing project owners to create an issue template."""

  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS
  _PAGE_TEMPLATE = 'tracker/template-create-page.ezt'
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

    #TODO(jojwang): call template_helpers.ParseTemplateRequest

    return urls.ADMIN_TEMPLATES
