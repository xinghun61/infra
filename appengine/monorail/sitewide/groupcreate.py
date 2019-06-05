# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A page for site admins to create a new user group."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import re

from framework import exceptions
from framework import framework_helpers
from framework import permissions
from framework import servlet
from proto import usergroup_pb2
from sitewide import group_helpers


class GroupCreate(servlet.Servlet):
  """Shows a page with a simple form to create a user group."""

  _PAGE_TEMPLATE = 'sitewide/group-create-page.ezt'

  def AssertBasePermission(self, mr):
    """Assert that the user has the permissions needed to view this page."""
    super(GroupCreate, self).AssertBasePermission(mr)

    if not permissions.CanCreateGroup(mr.perms):
      raise permissions.PermissionException(
          'User is not allowed to create a user group')

  def GatherPageData(self, _mr):
    """Build up a dictionary of data values to use when rendering the page."""
    visibility_levels = group_helpers.BuildUserGroupVisibilityOptions()
    initial_visibility = group_helpers.GroupVisibilityView(
        usergroup_pb2.MemberVisibility.ANYONE)
    group_types = group_helpers.BuildUserGroupTypeOptions()

    return {
        'groupadmin': '',
        'group_types': group_types,
        'import_group': '',
        'initial_friendprojects': '',
        'initial_group_type': '',
        'initial_name': '',
        'initial_visibility': initial_visibility,
        'visibility_levels': visibility_levels,
        }

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    # 1. Gather data from the request.
    group_name = post_data.get('groupname')
    try:
      existing_group_id = self.services.user.LookupUserID(mr.cnxn, group_name)
      existing_settings = self.services.usergroup.GetGroupSettings(
          mr.cnxn, existing_group_id)
      if existing_settings:
        mr.errors.groupname = 'That user group already exists'
    except exceptions.NoSuchUserException:
      pass

    if post_data.get('import_group'):
      vis = usergroup_pb2.MemberVisibility.OWNERS
      ext_group_type = post_data.get('group_type')
      friend_projects = ''
      if not ext_group_type:
        mr.errors.groupimport = 'Please provide external group type'
      else:
        ext_group_type = str(
            usergroup_pb2.GroupType(int(ext_group_type))).lower()

      if (ext_group_type == 'computed' and
          not group_name.startswith('everyone@')):
        mr.errors.groupimport = 'Computed groups must be named everyone@'

    else:
      vis = usergroup_pb2.MemberVisibility(int(post_data['visibility']))
      ext_group_type = None
      friend_projects = post_data.get('friendprojects', '')
    who_can_view_members = str(vis).lower()

    if not mr.errors.AnyErrors():
      project_ids, error = self.services.usergroup.ValidateFriendProjects(
          mr.cnxn, self.services, friend_projects)
      if error:
        mr.errors.friendprojects = error

    # 2. Call services layer to save changes.
    if not mr.errors.AnyErrors():
      group_id = self.services.usergroup.CreateGroup(
          mr.cnxn, self.services, group_name, who_can_view_members,
          ext_group_type, project_ids)

    # 3. Determine the next page in the UI flow.
    if mr.errors.AnyErrors():
      self.PleaseCorrect(mr, initial_name=group_name)
    else:
      # Go to the new user group's detail page.
      return framework_helpers.FormatAbsoluteURL(
          mr, '/g/%s/' % group_id, include_project=False)
