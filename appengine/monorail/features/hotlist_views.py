# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to display hotlists in templates."""

from third_party import ezt

from framework import framework_helpers
from framework import permissions
from framework import template_helpers


class MemberView(object):
  """EZT-view of details of how a person is participating in a project."""

  def __init__(self, logged_in_user_id, member_id, user_view, hotlist,
               effective_ids=None):
    """Initialize a MemberView with the given information.

    Args:
      logged_in_user_id: int user ID of the viewing user, or 0 for anon.
      member_id: int user ID of the hotlist member being viewed.
      user_ivew: UserView object for this member
      hotlist: Hotlist PB for the currently viewed hotlist
      effective_ids: optional set of user IDs for this user, if supplied
          we show the highest role that they have via any group membership.
    """

    self.viewing_self = ezt.boolean(logged_in_user_id == member_id)

    self.user = user_view
    member_qs_param = user_view.user_id
    self.detail_url = '/u/%s/' % member_qs_param
    self.role = framework_helpers.GetHotlistRoleName(
        effective_ids or {member_id}, hotlist)


class HotlistView(template_helpers.PBProxy):
  """Wrapper class that makes it easier to display a hotlist via EZT."""

  def __init__(
      self, hotlist_pb, user_auth=None,
      viewed_user_id=None, users_by_id=None, is_starred=False):
    super(HotlistView, self).__init__(hotlist_pb)

    self.visible = permissions.CanViewHotlist(
        user_auth.effective_ids, hotlist_pb)
    if not self.visible:
      return

    self.access_is_private = ezt.boolean(hotlist_pb.is_private)
    owner_id = hotlist_pb.owner_ids[0]  # only one owner allowed
    owner = users_by_id[owner_id]
    if owner.obscure_email:
      self.url = (
          '/u/%d/hotlists/%s' % (owner_id, hotlist_pb.name))
    else:
      self.url = (
          '/u/%s/hotlists/%s' % (
              owner.email, hotlist_pb.name))

    self.role_name = ''
    if viewed_user_id in hotlist_pb.owner_ids:
      self.role_name = 'owner'
    elif any(effective_id in hotlist_pb.editor_ids for
             effective_id in user_auth.effective_ids):
      self.role_name = 'editor'

    if users_by_id:
      self.owners = [users_by_id[owner_id] for
                     owner_id in hotlist_pb.owner_ids]
      self.editors = [users_by_id[editor_id] for
                      editor_id in hotlist_pb.editor_ids]
    self.num_issues = len(hotlist_pb.items)
    self.is_followed = ezt.boolean(user_auth.user_id in hotlist_pb.follower_ids)
    # TODO(jojwang): if hotlist follower's will not be used, perhaps change
    # from is_followed to is_member or just use is_starred
    self.num_followers = len(hotlist_pb.follower_ids)
    self.is_starred = ezt.boolean(is_starred)
