# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Page for showing a user's hotlists."""

from features import features_bizobj
from features import hotlist_views
from framework import framework_views
from framework import servlet

class UserHotlists(servlet.Servlet):
  """Servlet to display all of a user's hotlists."""

  _PAGE_TEMPLATE = 'features/user-hotlists.ezt'

  def GatherPageData(self, mr):
    hotlists = self.services.features.GetHotlistsByUserID(
        mr.cnxn, mr.viewed_user_auth.user_id)
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        features_bizobj.UsersInvolvedInHotlists(hotlists))
    views = [hotlist_views.HotlistView(
        hotlist_pb, mr.auth, mr.viewed_user_auth.user_id,
        users_by_id)
        for hotlist_pb in hotlists]
    visible_hotlists = [view for view in views if view.visible]
    owner_of_hotlists = [hotlist_view for hotlist_view in visible_hotlists
                         if hotlist_view.role_name == 'owner']
    editor_of_hotlists = [hotlist_view for hotlist_view in visible_hotlists
                          if hotlist_view.role_name == 'editor']
    follower_of_hotlists = [hotlist_view for hotlist_view in visible_hotlists
                         if hotlist_view.role_name == '']

    viewed_user_display_name = framework_views.GetViewedUserDisplayName(mr)

    return {
        'user_tab_mode': 'st6',
        'viewed_user_display_name': viewed_user_display_name,
        'owner_of_hotlists': owner_of_hotlists,
        'editor_of_hotlists': editor_of_hotlists,
        'follower_of_hotlists': follower_of_hotlists,
        }
