# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display user group admin page."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import time

from third_party import ezt

from framework import framework_helpers
from framework import permissions
from framework import servlet
from framework import urls
from proto import usergroup_pb2
from services import usergroup_svc
from sitewide import group_helpers


class GroupAdmin(servlet.Servlet):
  """The group admin page."""

  _PAGE_TEMPLATE = 'sitewide/group-admin-page.ezt'

  def AssertBasePermission(self, mr):
    """Assert that the user has the permissions needed to view this page."""
    super(GroupAdmin, self).AssertBasePermission(mr)

    _, owner_ids_dict = self.services.usergroup.LookupMembers(
        mr.cnxn, [mr.viewed_user_auth.user_id])
    owner_ids = owner_ids_dict[mr.viewed_user_auth.user_id]
    if not permissions.CanEditGroup(
        mr.perms, mr.auth.effective_ids, owner_ids):
      raise permissions.PermissionException(
          'User is not allowed to edit a user group')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    group_id = mr.viewed_user_auth.user_id
    group_settings = self.services.usergroup.GetGroupSettings(
        mr.cnxn, group_id)
    visibility_levels = group_helpers.BuildUserGroupVisibilityOptions()
    initial_visibility = group_helpers.GroupVisibilityView(
        group_settings.who_can_view_members)
    group_types = group_helpers.BuildUserGroupTypeOptions()
    import_group = bool(group_settings.ext_group_type)
    if import_group:
      initial_group_type = group_helpers.GroupTypeView(
          group_settings.ext_group_type)
    else:
      initial_group_type = ''

    if group_settings.friend_projects:
      initial_friendprojects = ', '.join(
          list(self.services.project.LookupProjectNames(
              mr.cnxn, group_settings.friend_projects).values()))
    else:
      initial_friendprojects = ''

    return {
        'admin_tab_mode': 'st2',
        'groupadmin': True,
        'groupid': group_id,
        'groupname': mr.viewed_username,
        'group_types': group_types,
        'import_group': import_group or '',
        'initial_friendprojects': initial_friendprojects,
        'initial_group_type': initial_group_type,
        'initial_visibility': initial_visibility,
        'offer_membership_editing': True,
        'visibility_levels': visibility_levels,
        }

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    # 1. Gather data from the request.
    group_name = mr.viewed_username
    group_id = mr.viewed_user_auth.user_id

    if post_data.get('import_group'):
      vis_level = usergroup_pb2.MemberVisibility.OWNERS
      ext_group_type = post_data.get('group_type')
      friend_projects = ''
      if not ext_group_type:
        mr.errors.groupimport = 'Please provide external group type'
      else:
        ext_group_type = usergroup_pb2.GroupType(int(ext_group_type))
    else:
      vis_level = post_data.get('visibility')
      ext_group_type = None
      friend_projects = post_data.get('friendprojects', '')
      if vis_level:
        vis_level = usergroup_pb2.MemberVisibility(int(vis_level))
      else:
        mr.errors.groupimport = 'Cannot update settings for imported group'

    if not mr.errors.AnyErrors():
      project_ids, error = self.services.usergroup.ValidateFriendProjects(
          mr.cnxn, self.services, friend_projects)
      if error:
        mr.errors.friendprojects = error

    # 2. Call services layer to save changes.
    if not mr.errors.AnyErrors():
      group_settings = usergroup_pb2.UserGroupSettings(
        who_can_view_members=vis_level,
        ext_group_type=ext_group_type,
        friend_projects=project_ids)
      self.services.usergroup.UpdateSettings(
          mr.cnxn, group_id, group_settings)

    # 3. Determine the next page in the UI flow.
    if mr.errors.AnyErrors():
      self.PleaseCorrect(mr, initial_name=group_name)
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, '/g/%s%s' % (group_name, urls.GROUP_ADMIN),
          include_project=False, saved=1, ts=int(time.time()))
