# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions used in user group modules."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from framework import framework_views
from proto import usergroup_pb2


class GroupVisibilityView(object):
  """Object for group visibility information that can be easily used in EZT."""

  VISIBILITY_NAMES = {
      usergroup_pb2.MemberVisibility.ANYONE: 'Anyone on the Internet',
      usergroup_pb2.MemberVisibility.MEMBERS: 'Group Members',
      usergroup_pb2.MemberVisibility.OWNERS: 'Group Owners'}

  def __init__(self, group_visibility_enum):
    self.key = int(group_visibility_enum)
    self.name = self.VISIBILITY_NAMES[group_visibility_enum]


class GroupTypeView(object):
  """Object for group type information that can be easily used in EZT."""

  TYPE_NAMES = {
      usergroup_pb2.GroupType.CHROME_INFRA_AUTH: 'Chrome-infra-auth',
      usergroup_pb2.GroupType.MDB: 'MDB',
      usergroup_pb2.GroupType.BAGGINS: 'Baggins',
      usergroup_pb2.GroupType.COMPUTED: 'Computed',
      }

  def __init__(self, group_type_enum):
    self.key = int(group_type_enum)
    self.name = self.TYPE_NAMES[group_type_enum]


class GroupMemberView(framework_views.UserView):
  """Wrapper class to display basic group member information in a template."""

  def __init__(self, user, group_id, role):
    assert role in ['member', 'owner']
    super(GroupMemberView, self).__init__(user)
    self.group_id = group_id
    self.role = role


def BuildUserGroupVisibilityOptions():
  """Return a list of user group visibility values for use in an HTML menu.

  Returns:
    A list of GroupVisibilityView objects that can be used in EZT.
  """
  vis_levels = [usergroup_pb2.MemberVisibility.OWNERS,
                usergroup_pb2.MemberVisibility.MEMBERS,
                usergroup_pb2.MemberVisibility.ANYONE]

  return [GroupVisibilityView(vis) for vis in vis_levels]


def BuildUserGroupTypeOptions():
  """Return a list of user group types for use in an HTML menu.

  Returns:
    A list of GroupTypeView objects that can be used in EZT.
  """
  group_types = [usergroup_pb2.GroupType.CHROME_INFRA_AUTH,
                 usergroup_pb2.GroupType.MDB,
                 usergroup_pb2.GroupType.BAGGINS,
                 usergroup_pb2.GroupType.COMPUTED]

  return sorted([GroupTypeView(gt) for gt in group_types],
                key=lambda gtv: gtv.name)
