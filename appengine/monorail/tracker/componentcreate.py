# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A servlet for project owners to create a new component def."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import time

from framework import framework_helpers
from framework import framework_views
from framework import jsonfeed
from framework import permissions
from framework import servlet
from framework import urls
from tracker import component_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_views

from third_party import ezt


class ComponentCreate(servlet.Servlet):
  """Servlet allowing project owners to create a component."""

  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS
  _PAGE_TEMPLATE = 'tracker/component-create-page.ezt'

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(ComponentCreate, self).AssertBasePermission(mr)
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
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        *[list(cd.admin_ids) + list(cd.cc_ids)
          for cd in config.component_defs])
    component_def_views = [
        tracker_views.ComponentDefView(mr.cnxn, self.services, cd, users_by_id)
        # TODO(jrobbins): future component-level view restrictions.
        for cd in config.component_defs]
    for cdv in component_def_views:
      setattr(cdv, 'selected', None)
      path = (cdv.parent_path + '>' + cdv.leaf_name).lstrip('>')
      if path == mr.component_path:
        setattr(cdv, 'selected', True)

    return {
        'parent_path': mr.component_path,
        'admin_tab_mode': servlet.Servlet.PROCESS_TAB_COMPONENTS,
        'component_defs': component_def_views,
        'initial_leaf_name': '',
        'initial_docstring': '',
        'initial_deprecated': ezt.boolean(False),
        'initial_admins': [],
        'initial_cc': [],
        'initial_labels': [],
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
    parent_path = post_data.get('parent_path', '')
    parsed = component_helpers.ParseComponentRequest(
        mr, post_data, self.services)

    if parent_path:
      parent_def = tracker_bizobj.FindComponentDef(parent_path, config)
      if not parent_def:
        self.abort(500, 'parent component not found')
      allow_parent_edit = permissions.CanEditComponentDef(
          mr.auth.effective_ids, mr.perms, mr.project, parent_def, config)
      if not allow_parent_edit:
        raise permissions.PermissionException(
            'User is not allowed to add a subcomponent here')

      path = '%s>%s' % (parent_path, parsed.leaf_name)
    else:
      path = parsed.leaf_name

    leaf_name_error_msg = LeafNameErrorMessage(
        parent_path, parsed.leaf_name, config)
    if leaf_name_error_msg:
      mr.errors.leaf_name = leaf_name_error_msg

    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, parent_path=parent_path,
          initial_leaf_name=parsed.leaf_name,
          initial_docstring=parsed.docstring,
          initial_deprecated=ezt.boolean(parsed.deprecated),
          initial_admins=parsed.admin_usernames,
          initial_cc=parsed.cc_usernames,
          initial_labels=parsed.label_strs,
      )
      return

    created = int(time.time())
    creator_id = self.services.user.LookupUserID(
        mr.cnxn, mr.auth.email, autocreate=False)

    self.services.config.CreateComponentDef(
        mr.cnxn, mr.project_id, path, parsed.docstring, parsed.deprecated,
        parsed.admin_ids, parsed.cc_ids, created, creator_id,
        label_ids=parsed.label_ids)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ADMIN_COMPONENTS, saved=1, ts=int(time.time()))


def LeafNameErrorMessage(parent_path, leaf_name, config):
  """Return an error message for the given component name, or None."""
  if not tracker_constants.COMPONENT_NAME_RE.match(leaf_name):
    return 'Invalid component name'

  if parent_path:
    path = '%s>%s' % (parent_path, leaf_name)
  else:
    path = leaf_name

  if tracker_bizobj.FindComponentDef(path, config):
    return 'That name is already in use.'

  return None
