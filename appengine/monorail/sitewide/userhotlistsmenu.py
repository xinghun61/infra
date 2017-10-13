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

    with mr.profiler.Phase('page processing'):
      json_data.update(self._GatherHotlists(mr))

    return json_data

  def _GatherHotlists(self, mr):
    """Return a dict of hotlist names the current user is involved in."""
    with mr.profiler.Phase('GetUserHotlists'):
      user_hotlists = self.services.features.GetHotlistsByUserID(
          mr.cnxn, mr.auth.user_id)

      user_starred_hids = self.services.hotlist_star.LookupStarredItemIDs(
          mr.cnxn, mr.auth.user_id)
      user_starred_hotlists, _ = self.services.features.GetHotlistsByID(
          mr.cnxn, user_starred_hids)

      recently_visited_hids = self.services.user.GetRecentlyVisitedHotlists(
          mr.cnxn, mr.auth.user_id)
      recently_visited_hotlists, _ = self.services.features.GetHotlistsByID(
          mr.cnxn, [hid for hid in recently_visited_hids])

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
                                 mr.auth.effective_ids, h) and
                             h not in user_hotlists],
        'visited_hotlists': [(recently_visited_hotlists[hid].name,
                              hotlist_helpers.GetURLOfHotlist(
                                  mr.cnxn, recently_visited_hotlists[hid],
                                  self.services.user)) for
                             hid in recently_visited_hids if
                             recently_visited_hotlists[hid] not in user_hotlists
                             and hid not in user_starred_hids],
        'user': mr.auth.email
        }
    return hotlists_dict
