# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions and classes used by the hotlist pages."""

def MembersWithoutGivenIDs(hotlist, exclude_ids):
  """Return three lists of member user IDs, with exclude_ids not in them."""
  owner_ids = [user_id for user_id in hotlist.owner_ids
               if user_id not in exclude_ids]
  editor_ids = [user_id for user_id in hotlist.editor_ids
                   if user_id not in exclude_ids]
  follower_ids = [user_id for user_id in hotlist.follower_ids
                     if user_id not in exclude_ids]

  return owner_ids, editor_ids, follower_ids


def MembersWithGivenIDs(hotlist, new_member_ids, role):
  """Return three lists of member IDs with the new IDs in the right one.

  Args:
    hotlist: Hotlist PB for the project to get current members from.
    new_member_ids: set of user IDs for members being added.
    role: string name of the role that new_member_ids should be granted.

  Returns:
    Three lists of member IDs with new_member_ids added to the appropriate
    list and removed from any other role.

  Raises:
    ValueError: if the role is not one of owner, committer, or contributor.
  """
  owner_ids, editor_ids, follower_ids = MembersWithoutGivenIDs(
      hotlist, new_member_ids)

  if role == 'owner':
    owner_ids.extend(new_member_ids)
  elif role == 'editor':
    editor_ids.extend(new_member_ids)
  elif role == 'follower':
    follower_ids.extend(new_member_ids)
  else:
    raise ValueError()

  return owner_ids, editor_ids, follower_ids
