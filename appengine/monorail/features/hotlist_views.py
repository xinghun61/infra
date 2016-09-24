# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to display hotlists in templates."""

import ezt

from framework import permissions
from framework import template_helpers


class HotlistView(template_helpers.PBProxy):
  """Wrapper class that makes it easier to display a hotlist via EZT."""

  def __init__(
      self, hotlist_pb, logged_in_user_id=None, viewed_user_id=None,
      user_ids_to_names=None):
    super(HotlistView, self).__init__(hotlist_pb)

    # TODO(lukasperaza): pass user's effective IDs to CanViewHotlist instead
    # of just the user's ID
    self.visible = permissions.CanViewHotlist({logged_in_user_id}, hotlist_pb)
    if not self.visible:
      return

    self.url = (
        '/u/%d/hotlists/%d' % (hotlist_pb.owner_ids[0], hotlist_pb.hotlist_id))
    owner_name = user_ids_to_names[hotlist_pb.owner_ids[0]]
    self.friendly_url = (
        '/u/%s/hotlists/%s' % (
            owner_name, hotlist_pb.name.lower().replace(' ', '-')))

    self.role_name = ''
    if viewed_user_id in hotlist_pb.owner_ids:
      self.role_name = 'owner'
    elif viewed_user_id in hotlist_pb.editor_ids:
      self.role_name = 'editor'

    self.num_issues = len(hotlist_pb.iid_rank_pairs)
    self.is_starred = ezt.boolean(logged_in_user_id in hotlist_pb.follower_ids)
