# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes for the user settings (preferences) page."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time
import urllib

from third_party import ezt

from businesslogic import work_env
from framework import framework_helpers
from framework import permissions
from framework import servlet
from framework import template_helpers
from framework import urls


class UserSettings(servlet.Servlet):
  """Shows a page with a simple form to edit user preferences."""

  _PAGE_TEMPLATE = 'sitewide/user-settings-page.ezt'

  def AssertBasePermission(self, mr):
    """Assert that the user has the permissions needed to view this page."""
    super(UserSettings, self).AssertBasePermission(mr)

    if not mr.auth.user_id:
      raise permissions.PermissionException(
          'Anonymous users are not allowed to edit user settings')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    page_data = {
        'user_tab_mode': 'st3',
        'logged_in_user_pb': template_helpers.PBProxy(mr.auth.user_pb),
        # When on /hosting/settings, the logged-in user is the viewed user.
        'viewed_user': mr.auth.user_view,
        'offer_saved_queries_subtab': ezt.boolean(True),
        'viewing_self': ezt.boolean(True),
        }
    with work_env.WorkEnv(mr, self.services) as we:
      settings_user_prefs = we.GetUserPrefs(mr.auth.user_id)
    page_data.update(
        framework_helpers.UserSettings.GatherUnifiedSettingsPageData(
            mr.auth.user_id, mr.auth.user_view, mr.auth.user_pb,
            settings_user_prefs))
    return page_data

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    with work_env.WorkEnv(mr, self.services) as we:
      framework_helpers.UserSettings.ProcessSettingsForm(
          we, post_data, mr.auth.user_pb)

    url = framework_helpers.FormatAbsoluteURL(
        mr, urls.USER_SETTINGS, include_project=False,
        saved=1, ts=int(time.time()))

    return url
