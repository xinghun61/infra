# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Page for showing a user's saved queries and subscription options."""

import logging
import time

from third_party import ezt

from features import savedqueries_helpers
from framework import framework_helpers
from framework import permissions
from framework import servlet
from framework import urls


class SavedQueries(servlet.Servlet):
  """A page class that shows the user's saved queries."""

  _PAGE_TEMPLATE = 'features/saved-queries-page.ezt'

  def AssertBasePermission(self, mr):
    super(SavedQueries, self).AssertBasePermission(mr)
    viewing_self = mr.viewed_user_auth.user_id == mr.auth.user_id
    if not mr.auth.user_pb.is_site_admin and not viewing_self:
      raise permissions.PermissionException(
          'User not allowed to edit this user\'s saved queries')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    saved_queries = self.services.features.GetSavedQueriesByUserID(
        mr.cnxn, mr.viewed_user_auth.user_id)
    saved_query_views = [
        savedqueries_helpers.SavedQueryView(
            sq, idx + 1, mr.cnxn, self.services.project)
        for idx, sq in enumerate(saved_queries)]

    page_data = {
        'canned_queries': saved_query_views,
        'new_query_indexes': (
            range(len(saved_queries) + 1,
                  savedqueries_helpers.MAX_QUERIES + 1)),
        'max_queries': savedqueries_helpers.MAX_QUERIES,
        'user_tab_mode': 'st4',
        'viewing_user_page': ezt.boolean(True),
        }
    return page_data

  def ProcessFormData(self, mr, post_data):
    """Validate and store the contents of the issues tracker admin page.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """
    existing_queries = savedqueries_helpers.ParseSavedQueries(
        mr.cnxn, post_data, self.services.project)
    added_queries = savedqueries_helpers.ParseSavedQueries(
        mr.cnxn, post_data, self.services.project, prefix='new_')
    saved_queries = existing_queries + added_queries

    self.services.features.UpdateUserSavedQueries(
        mr.cnxn, mr.viewed_user_auth.user_id, saved_queries)

    return framework_helpers.FormatAbsoluteURL(
        mr, '/u/%s%s' % (mr.viewed_username, urls.SAVED_QUERIES),
        include_project=False, saved=1, ts=int(time.time()))
