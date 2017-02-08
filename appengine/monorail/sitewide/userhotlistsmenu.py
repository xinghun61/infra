# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes for the user hotlists feed."""

from features import hotlist_helpers
from framework import jsonfeed
from framework import permissions


class HotlistsJsonFeed(jsonfeed.JsonFeed):
  """Servlet to get all of a user's hotlists in JSON format."""

  def HandleRequest(self, mr):
    """Retrieve list of a user's hotlists for the "My hotlists" menu.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format
    """

    if not mr.auth.user_id:
      return {'error': 'User is not logged in.'}

    json_data = {}

    with self.profiler.Phase('page processing'):
      json_data.update(self._GatherHotlists(mr))

    return json_data

  def _GatherHotlists(self, mr):
    """Return a dict of hotlist names the current user is involved in."""
    with self.profiler.Phase('GetUserHotlists'):
      user_hotlists = self.services.features.GetHotlistsByUserID(
          mr.cnxn, mr.auth.user_id)
      user_starred_hids = self.services.hotlist_star.LookupStarredItemIDs(
          mr.cnxn, mr.auth.user_id)
      user_starred_hotlists, _ = self.services.features.GetHotlistsByID(
          mr.cnxn, user_starred_hids)

    hotlists_dict = {
        'ownerof': [(h.name, hotlist_helpers.GetURLOfHotlist(
            mr.cnxn, h, self.services.user)) for
                    h in user_hotlists if mr.auth.user_id in h.owner_ids],
        'editorof': [(h.name, hotlist_helpers.GetURLOfHotlist(
            mr.cnxn, h, self.services.user)) for
                     h in user_hotlists if mr.auth.user_id in h.editor_ids],
        'starred_hotlists': [(h.name, hotlist_helpers.GetURLOfHotlist(
            mr.cnxn, h, self.services.user)) for
                             h in user_starred_hotlists.values() if
                             permissions.CanViewHotlist(
                                 mr.auth.effective_ids, h)],
        'user': mr.auth.email
        }
    return hotlists_dict
