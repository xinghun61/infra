# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Protocol buffers for Monorail usergroups."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from protorpc import messages


class MemberVisibility(messages.Enum):
  """Enum controlling who can see the members of a user group."""
  OWNERS = 0
  MEMBERS = 1
  ANYONE = 2


class GroupType(messages.Enum):
  """Type of external group to import."""
  CHROME_INFRA_AUTH = 0
  MDB = 1
  BAGGINS = 3
  COMPUTED = 4


class UserGroupSettings(messages.Message):
  """In-memory busines object for representing user group settings."""
  who_can_view_members = messages.EnumField(
      MemberVisibility, 1, default=MemberVisibility.MEMBERS)
  ext_group_type = messages.EnumField(GroupType, 2)
  last_sync_time = messages.IntegerField(
      3, default=0, variant=messages.Variant.INT32)
  friend_projects = messages.IntegerField(
      4, repeated=True, variant=messages.Variant.INT32)
  notify_members = messages.BooleanField(5, default=True)
  notify_group = messages.BooleanField(6, default=False)
# TODO(jrobbins): add settings to control who can join, etc.


def MakeSettings(who_can_view_members_str, ext_group_type_str=None,
                 last_sync_time=0, friend_projects=None, notify_members=True,
                 notify_group=False):
  """Create and return a new user record in RAM."""
  settings = UserGroupSettings(
      who_can_view_members=MemberVisibility(who_can_view_members_str.upper()),
      notify_members=notify_members, notify_group=notify_group)
  if ext_group_type_str:
    settings.ext_group_type = GroupType(ext_group_type_str.upper())
  settings.last_sync_time = last_sync_time
  settings.friend_projects = friend_projects or []
  return settings
