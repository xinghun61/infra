# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Page for showing a user's hotlists."""

from third_party import ezt

from features import features_bizobj
from features import hotlist_views
from framework import framework_views
from framework import servlet


class UserHotlists(servlet.Servlet):
  """Servlet to display all of a user's hotlists."""

  _PAGE_TEMPLATE = 'features/user-hotlists.ezt'

  def GatherPageData(self, mr):
    viewed_users_hotlists = self.services.features.GetHotlistsByUserID(
        mr.cnxn, mr.viewed_user_auth.user_id)

    viewed_starred_hids = self.services.hotlist_star.LookupStarredItemIDs(
        mr.cnxn, mr.viewed_user_auth.user_id)
    viewed_users_starred_hotlists, _ = self.services.features.GetHotlistsByID(
        mr.cnxn, viewed_starred_hids)

    viewed_users_relevant_hotlists = viewed_users_hotlists + list(
        set(viewed_users_starred_hotlists.values()) -
        set(viewed_users_hotlists))

    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        features_bizobj.UsersInvolvedInHotlists(viewed_users_relevant_hotlists))

    views = [hotlist_views.HotlistView(
        hotlist_pb, mr.auth, mr.viewed_user_auth.user_id,
        users_by_id, self.services.hotlist_star.IsItemStarredBy(
            mr.cnxn, hotlist_pb.hotlist_id, mr.auth.user_id))
        for hotlist_pb in viewed_users_relevant_hotlists]

    # visible to viewer, not viewed_user
    visible_hotlists = [view for view in views if view.visible]

    owner_of_hotlists = [hotlist_view for hotlist_view in visible_hotlists
                         if hotlist_view.role_name == 'owner']
    editor_of_hotlists = [hotlist_view for hotlist_view in visible_hotlists
                          if hotlist_view.role_name == 'editor']
    follower_of_hotlists = [hotlist_view for hotlist_view in visible_hotlists
                         if hotlist_view.role_name == '']
    starred_hotlists = [hotlist_view for hotlist_view in visible_hotlists
                        if hotlist_view.hotlist_id in viewed_starred_hids]

    viewed_user_display_name = framework_views.GetViewedUserDisplayName(mr)

    return {
        'user_tab_mode': 'st6',
        'viewed_user_display_name': viewed_user_display_name,
        'owner_of_hotlists': owner_of_hotlists,
        'editor_of_hotlists': editor_of_hotlists,
        'follower_of_hotlists': follower_of_hotlists,
        'starred_hotlists': starred_hotlists,
        'viewing_user_page': ezt.boolean(True),
        }

  def GatherHelpData(self, mr, page_data):
    """Return a dict of values to drive on-page user help.

    Args:
      mr: common information parsed from the HTTP request.
      page_data: Dictionary of base and page template data.

    Returns:
      A dict of values to drive on-page user help, to be added to page_data.
    """
    help_data = super(UserHotlists, self).GatherHelpData(mr, page_data)
    help_data['cue'] = 'explain_hotlist_starring'
    return help_data
