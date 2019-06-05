# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to list user groups."""
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
from framework import xsrf
from sitewide import sitewide_views


class GroupList(servlet.Servlet):
  """Shows a page with a simple form to create a user group."""

  _PAGE_TEMPLATE = 'sitewide/group-list-page.ezt'

  def AssertBasePermission(self, mr):
    """Assert that the user has the permissions needed to view this page."""
    super(GroupList, self).AssertBasePermission(mr)

    if not mr.perms.HasPerm(permissions.VIEW_GROUP, None, None):
      raise permissions.PermissionException(
          'User is not allowed to view list of user groups')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    group_views = [
        sitewide_views.GroupView(*groupinfo) for groupinfo in
        self.services.usergroup.GetAllUserGroupsInfo(mr.cnxn)]
    group_views.sort(key=lambda gv: gv.name)
    offer_group_deletion = mr.perms.CanUsePerm(
        permissions.DELETE_GROUP, mr.auth.effective_ids, None, [])
    offer_group_creation = mr.perms.CanUsePerm(
        permissions.CREATE_GROUP, mr.auth.effective_ids, None, [])

    return {
        'form_token': xsrf.GenerateToken(
            mr.auth.user_id, '%s.do' % urls.GROUP_DELETE),
        'groups': group_views,
        'offer_group_deletion': ezt.boolean(offer_group_deletion),
        'offer_group_creation': ezt.boolean(offer_group_creation),
        }

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    if 'removebtn' in post_data:
      return self.ProcessDeleteGroups(mr, post_data)

  def ProcessDeleteGroups(self, mr, post_data):
    """Process request to delete groups."""
    if not mr.perms.CanUsePerm(
        permissions.DELETE_GROUP, mr.auth.effective_ids, None, []):
      raise permissions.PermissionException(
          'User is not permitted to delete groups')

    remove_groups = [int(g) for g in post_data.getall('remove')]

    if not mr.errors.AnyErrors():
      self.services.usergroup.DeleteGroups(mr.cnxn, remove_groups)

    if mr.errors.AnyErrors():
      self.PleaseCorrect(mr)
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, '/g', include_project=False,
          saved=1, ts=int(time.time()))
