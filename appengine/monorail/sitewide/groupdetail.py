# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display a user group, including a paginated list of members."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import time

from third_party import ezt

from framework import exceptions
from framework import framework_helpers
from framework import framework_views
from framework import paginate
from framework import permissions
from framework import servlet
from project import project_helpers
from proto import usergroup_pb2
from sitewide import group_helpers
from sitewide import sitewide_views

MEMBERS_PER_PAGE = 50


class GroupDetail(servlet.Servlet):
  """The group detail page presents information about one user group."""

  _PAGE_TEMPLATE = 'sitewide/group-detail-page.ezt'

  def AssertBasePermission(self, mr):
    """Assert that the user has the permissions needed to view this page."""
    super(GroupDetail, self).AssertBasePermission(mr)

    group_id = mr.viewed_user_auth.user_id
    group_settings = self.services.usergroup.GetGroupSettings(
        mr.cnxn, group_id)
    if not group_settings:
      return

    member_ids, owner_ids = self.services.usergroup.LookupAllMembers(
          mr.cnxn, [group_id])
    (owned_project_ids, membered_project_ids,
     contrib_project_ids) = self.services.project.GetUserRolesInAllProjects(
         mr.cnxn, mr.auth.effective_ids)
    project_ids = owned_project_ids.union(
        membered_project_ids).union(contrib_project_ids)
    if not permissions.CanViewGroupMembers(
        mr.perms, mr.auth.effective_ids, group_settings, member_ids[group_id],
        owner_ids[group_id], project_ids):
      raise permissions.PermissionException(
          'User is not allowed to view a user group')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    group_id = mr.viewed_user_auth.user_id
    group_settings = self.services.usergroup.GetGroupSettings(
        mr.cnxn, group_id)
    if not group_settings:
      raise exceptions.NoSuchGroupException()

    member_ids_dict, owner_ids_dict = (
        self.services.usergroup.LookupVisibleMembers(
            mr.cnxn, [group_id], mr.perms, mr.auth.effective_ids,
            self.services))
    member_ids = member_ids_dict[group_id]
    owner_ids = owner_ids_dict[group_id]
    member_pbs_dict = self.services.user.GetUsersByIDs(
        mr.cnxn, member_ids)
    owner_pbs_dict = self.services.user.GetUsersByIDs(
        mr.cnxn, owner_ids)
    member_dict = {}
    for user_id, user_pb in member_pbs_dict.items():
      member_view = group_helpers.GroupMemberView(user_pb, group_id, 'member')
      member_dict[user_id] = member_view
    owner_dict = {}
    for user_id, user_pb in owner_pbs_dict.items():
      member_view = group_helpers.GroupMemberView(user_pb, group_id, 'owner')
      owner_dict[user_id] = member_view

    member_user_views = []
    member_user_views.extend(
        sorted(list(owner_dict.values()), key=lambda u: u.email))
    member_user_views.extend(
        sorted(list(member_dict.values()), key=lambda u: u.email))

    group_view = sitewide_views.GroupView(
        mr.viewed_user_auth.email, len(member_ids), group_settings,
        mr.viewed_user_auth.user_id)
    url_params = [(name, mr.GetParam(name)) for name in
                  framework_helpers.RECOGNIZED_PARAMS]
    pagination = paginate.ArtifactPagination(
        member_user_views, mr.GetPositiveIntParam('num', MEMBERS_PER_PAGE),
        mr.GetPositiveIntParam('start'), mr.project_name, group_view.detail_url,
        url_params=url_params)

    is_imported_group = bool(group_settings.ext_group_type)

    offer_membership_editing = permissions.CanEditGroup(
        mr.perms, mr.auth.effective_ids, owner_ids) and not is_imported_group

    group_type = 'Monorail user group'
    if group_settings.ext_group_type:
      group_type = str(group_settings.ext_group_type).capitalize()

    return {
        'admin_tab_mode': self.ADMIN_TAB_META,
        'offer_membership_editing': ezt.boolean(offer_membership_editing),
        'initial_add_members': '',
        'initially_expand_form': ezt.boolean(False),
        'groupid': group_id,
        'groupname': mr.viewed_username,
        'settings': group_settings,
        'group_type': group_type,
        'pagination': pagination,
        }

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    _, owner_ids_dict = self.services.usergroup.LookupMembers(
        mr.cnxn, [mr.viewed_user_auth.user_id])
    owner_ids = owner_ids_dict[mr.viewed_user_auth.user_id]
    permit_edit = permissions.CanEditGroup(
        mr.perms, mr.auth.effective_ids, owner_ids)
    if not permit_edit:
      raise permissions.PermissionException(
          'User is not permitted to edit group membership')

    group_settings = self.services.usergroup.GetGroupSettings(
        mr.cnxn, mr.viewed_user_auth.user_id)
    if bool(group_settings.ext_group_type):
      raise permissions.PermissionException(
          'Imported groups are read-only')

    if 'addbtn' in post_data:
      return self.ProcessAddMembers(mr, post_data)
    elif 'removebtn' in post_data:
      return self.ProcessRemoveMembers(mr, post_data)

  def ProcessAddMembers(self, mr, post_data):
    """Process the user's request to add members.

    Args:
      mr: common information parsed from the HTTP request.
      post_data: dictionary of form data.

    Returns:
      String URL to redirect the user to after processing.
    """
    # 1. Gather data from the request.
    group_id = mr.viewed_user_auth.user_id
    add_members_str = post_data.get('addmembers')
    new_member_ids = project_helpers.ParseUsernames(
        mr.cnxn, self.services.user, add_members_str)
    role = post_data['role']

    # 2. Call services layer to save changes.
    if not mr.errors.AnyErrors():
      try:
        self.services.usergroup.UpdateMembers(
            mr.cnxn, group_id, new_member_ids, role)
      except exceptions.CircularGroupException:
        mr.errors.addmembers = (
            'The members are already ancestors of current group.')

    # 3. Determine the next page in the UI flow.
    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, initial_add_members=add_members_str,
          initially_expand_form=ezt.boolean(True))
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, '/g/%s/' % mr.viewed_username, include_project=False,
          saved=1, ts=int(time.time()))

  def ProcessRemoveMembers(self, mr, post_data):
    """Process the user's request to remove members.

    Args:
      mr: common information parsed from the HTTP request.
      post_data: dictionary of form data.

    Returns:
      String URL to redirect the user to after processing.
    """
    # 1. Gather data from the request.
    remove_strs = post_data.getall('remove')
    logging.info('remove_strs = %r', remove_strs)

    if not remove_strs:
      mr.errors.remove = 'No users specified'

    # 2. Call services layer to save changes.
    if not mr.errors.AnyErrors():
      remove_ids = set(
          self.services.user.LookupUserIDs(mr.cnxn, remove_strs).values())
      self.services.usergroup.RemoveMembers(
          mr.cnxn, mr.viewed_user_auth.user_id, remove_ids)

    # 3. Determine the next page in the UI flow.
    if mr.errors.AnyErrors():
      self.PleaseCorrect(mr)
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, '/g/%s/' % mr.viewed_username, include_project=False,
          saved=1, ts=int(time.time()))
