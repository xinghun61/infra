# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A servlet for project and component owners to view and edit components."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import time

from third_party import ezt

from features import filterrules_helpers
from framework import framework_helpers
from framework import framework_views
from framework import permissions
from framework import servlet
from framework import timestr
from framework import urls
from tracker import component_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_views


class ComponentDetail(servlet.Servlet):
  """Servlets allowing project owners to view and edit a component."""

  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS
  _PAGE_TEMPLATE = 'tracker/component-detail-page.ezt'

  def _GetComponentDef(self, mr):
    """Get the config and component definition to be viewed or edited."""
    if not mr.component_path:
      self.abort(404, 'component not specified')
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    component_def = tracker_bizobj.FindComponentDef(mr.component_path, config)
    if not component_def:
      self.abort(404, 'component not found')
    return config, component_def

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(ComponentDetail, self).AssertBasePermission(mr)
    _config, component_def = self._GetComponentDef(mr)

    # TODO(jrobbins): optional restrictions on viewing fields by component.

    allow_view = permissions.CanViewComponentDef(
        mr.auth.effective_ids, mr.perms, mr.project, component_def)
    if not allow_view:
      raise permissions.PermissionException(
          'User is not allowed to view this component')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    config, component_def = self._GetComponentDef(mr)
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        component_def.admin_ids, component_def.cc_ids)
    component_def_view = tracker_views.ComponentDefView(
        mr.cnxn, self.services, component_def, users_by_id)
    initial_admins = [users_by_id[uid].email for uid in component_def.admin_ids]
    initial_cc = [users_by_id[uid].email for uid in component_def.cc_ids]
    initial_labels = [
        self.services.config.LookupLabel(mr.cnxn, mr.project_id, label_id)
        for label_id in component_def.label_ids]

    creator, created = self._GetUserViewAndFormattedTime(
        mr, component_def.creator_id, component_def.created)
    modifier, modified = self._GetUserViewAndFormattedTime(
        mr, component_def.modifier_id, component_def.modified)

    allow_edit = permissions.CanEditComponentDef(
        mr.auth.effective_ids, mr.perms, mr.project, component_def, config)

    subcomponents = tracker_bizobj.FindDescendantComponents(
        config, component_def)
    templates = self.services.template.TemplatesWithComponent(
        mr.cnxn, component_def.component_id)
    allow_delete = allow_edit and not subcomponents and not templates

    return {
        'admin_tab_mode': servlet.Servlet.PROCESS_TAB_COMPONENTS,
        'component_def': component_def_view,
        'initial_leaf_name': component_def_view.leaf_name,
        'initial_docstring': component_def.docstring,
        'initial_deprecated': ezt.boolean(component_def.deprecated),
        'initial_admins': initial_admins,
        'initial_cc': initial_cc,
        'initial_labels': initial_labels,
        'allow_edit': ezt.boolean(allow_edit),
        'allow_delete': ezt.boolean(allow_delete),
        'subcomponents': subcomponents,
        'templates': templates,
        'creator': creator,
        'created': created,
        'modifier': modifier,
        'modified': modified,
        }

  def ProcessFormData(self, mr, post_data):
    """Validate and store the contents of the issues tracker admin page.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """
    config, component_def = self._GetComponentDef(mr)
    allow_edit = permissions.CanEditComponentDef(
        mr.auth.effective_ids, mr.perms, mr.project, component_def, config)
    if not allow_edit:
      raise permissions.PermissionException(
          'User is not allowed to edit or delete this component')

    if 'deletecomponent' in post_data:
      allow_delete = not tracker_bizobj.FindDescendantComponents(
          config, component_def)
      if not allow_delete:
        raise permissions.PermissionException(
            'User tried to delete component that had subcomponents')
      return self._ProcessDeleteComponent(mr, component_def)

    else:
      return self._ProcessEditComponent(mr, post_data, config, component_def)


  def _ProcessDeleteComponent(self, mr, component_def):
    """The user wants to delete the specified custom field definition."""
    self.services.issue.DeleteComponentReferences(
        mr.cnxn, component_def.component_id)
    self.services.config.DeleteComponentDef(
        mr.cnxn, mr.project_id, component_def.component_id)
    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ADMIN_COMPONENTS, deleted=1, ts=int(time.time()))

  def _GetUserViewAndFormattedTime(self, mr, user_id, timestamp):
    formatted_time = (timestr.FormatAbsoluteDate(timestamp)
                      if timestamp else None)
    user = self.services.user.GetUser(mr.cnxn, user_id) if user_id else None
    user_view = None
    if user:
      user_view = framework_views.UserView(user)
      viewing_self = mr.auth.user_id == user_id
      # Do not obscure email if current user is a site admin. Do not obscure
      # email if current user is the same as the creator. For all other
      # cases do whatever obscure_email setting for the user is.
      email_obscured = (not(mr.auth.user_pb.is_site_admin or viewing_self)
                        and user_view.obscure_email)
      if not email_obscured:
        user_view.RevealEmail()

    return user_view, formatted_time

  def _ProcessEditComponent(self, mr, post_data, config, component_def):
    """The user wants to edit this component definition."""
    parsed = component_helpers.ParseComponentRequest(
        mr, post_data, self.services)

    if not tracker_constants.COMPONENT_NAME_RE.match(parsed.leaf_name):
      mr.errors.leaf_name = 'Invalid component name'

    original_path = component_def.path
    if mr.component_path and '>' in mr.component_path:
      parent_path = mr.component_path[:mr.component_path.rindex('>')]
      new_path = '%s>%s' % (parent_path, parsed.leaf_name)
    else:
      new_path = parsed.leaf_name

    conflict = tracker_bizobj.FindComponentDef(new_path, config)
    if conflict and conflict.component_id != component_def.component_id:
      mr.errors.leaf_name = 'That name is already in use.'

    creator, created = self._GetUserViewAndFormattedTime(
        mr, component_def.creator_id, component_def.created)
    modifier, modified = self._GetUserViewAndFormattedTime(
        mr, component_def.modifier_id, component_def.modified)

    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, initial_leaf_name=parsed.leaf_name,
          initial_docstring=parsed.docstring,
          initial_deprecated=ezt.boolean(parsed.deprecated),
          initial_admins=parsed.admin_usernames,
          initial_cc=parsed.cc_usernames,
          initial_labels=parsed.label_strs,
          created=created,
          creator=creator,
          modified=modified,
          modifier=modifier,
      )
      return None

    new_modified = int(time.time())
    new_modifier_id = self.services.user.LookupUserID(
        mr.cnxn, mr.auth.email, autocreate=False)
    self.services.config.UpdateComponentDef(
        mr.cnxn, mr.project_id, component_def.component_id,
        path=new_path, docstring=parsed.docstring, deprecated=parsed.deprecated,
        admin_ids=parsed.admin_ids, cc_ids=parsed.cc_ids, modified=new_modified,
        modifier_id=new_modifier_id, label_ids=parsed.label_ids)

    update_rule = False
    if new_path != original_path:
      update_rule = True
      # If the name changed then update all of its subcomponents as well.
      subcomponent_ids = tracker_bizobj.FindMatchingComponentIDs(
          original_path, config, exact=False)
      for subcomponent_id in subcomponent_ids:
        if subcomponent_id == component_def.component_id:
          continue
        subcomponent_def = tracker_bizobj.FindComponentDefByID(
            subcomponent_id, config)
        subcomponent_new_path = subcomponent_def.path.replace(
            original_path, new_path, 1)
        self.services.config.UpdateComponentDef(
            mr.cnxn, mr.project_id, subcomponent_def.component_id,
            path=subcomponent_new_path)

    if (set(parsed.cc_ids) != set(component_def.cc_ids) or
        set(parsed.label_ids) != set(component_def.label_ids)):
      update_rule = True
    if update_rule:
      filterrules_helpers.RecomputeAllDerivedFields(
          mr.cnxn, self.services, mr.project, config)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.COMPONENT_DETAIL,
        component=new_path, saved=1, ts=int(time.time()))
