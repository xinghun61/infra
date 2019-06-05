# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Class to show a servlet to clear a user's bouncing email timestamp."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import time

from framework import framework_helpers
from framework import permissions
from framework import servlet
from framework import timestr


class UserClearBouncing(servlet.Servlet):
  """Shows a page that can clear a user's bouncing email timestamp."""

  _PAGE_TEMPLATE = 'sitewide/user-clear-bouncing-page.ezt'

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(UserClearBouncing, self).AssertBasePermission(mr)
    if mr.auth.user_id == mr.viewed_user_auth.user_id:
      return
    if mr.perms.HasPerm(permissions.EDIT_OTHER_USERS, None, None):
      return
    raise permissions.PermissionException('You cannot edit this user.')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    viewed_user = mr.viewed_user_auth.user_pb
    if viewed_user.email_bounce_timestamp:
      last_bounce_str = timestr.FormatRelativeDate(
          viewed_user.email_bounce_timestamp, days_only=True)
      last_bounce_str = last_bounce_str or 'Less than 2 days ago'
    else:
      last_bounce_str = None

    page_data = {
        'user_tab_mode': 'st2',
        'last_bounce_str': last_bounce_str,
        }
    return page_data

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    viewed_user = mr.viewed_user_auth.user_pb
    viewed_user.email_bounce_timestamp = None
    self.services.user.UpdateUser(
        mr.cnxn, viewed_user.user_id, viewed_user)
    return framework_helpers.FormatAbsoluteURL(
        mr, mr.viewed_user_auth.user_view.profile_url, include_project=False,
        saved=1, ts=int(time.time()))
