# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to implement the hotlistpeople page and related forms."""

from framework import servlet

class HotlistPeopleList(servlet.Servlet):
  _PAGE_TEMPLATE = ''
  # TODO(jojwang):create a hotlist-people-page template

  def AssertBasePermission(self, mr):
    super(HotlistPeopleList, self).AssertBasePermission(mr)
    #TODO(jojwang): more permissions stuff

  def GatherPageData(self, mr):
    pass
    # TODO(jojwang): pagination,

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    pass

  def ProcessAddMembers(self, mr, post_data):
    """Process the user's request to add members.

    Args:
      mr: common information parsed from the HTTP request.
      post_data: dictionary of form data

    Returns:
      String URL to redirect the user to after processing
    """
    pass

# TODO(jojwang): implement/add more functions
# TODO(jojwang): add _MakeMemberViews(self, logged_in_user_id
# users_by_id, member_ids, hotlists):
