# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes for user updates pages.

  AbstractUserUpdatesPage: Base class for all user updates pages
  UserUpdatesProjects: Handles displaying starred projects
  UserUpdatesDevelopers: Handles displaying starred developers
  UserUpdatesIndividual: Handles displaying activities by the viewed user
"""


import logging

from third_party import ezt

from businesslogic import work_env
from features import activities
from framework import servlet
from framework import urls
from sitewide import sitewide_helpers


class AbstractUserUpdatesPage(servlet.Servlet):
  """Base class for user updates pages."""

  _PAGE_TEMPLATE = 'sitewide/user-updates-page.ezt'

  # Subclasses should override these constants.
  _UPDATES_PAGE_URL = None
  # What to highlight in the middle column on user updates pages - 'project',
  # 'user', or None
  _HIGHLIGHT = None
  # What the ending phrase for activity titles should be - 'by_user',
  # 'in_project', or None
  _ENDING = None
  _TAB_MODE = None

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    # TODO(jrobbins): re-implement
    # if self.CheckRevelationCaptcha(mr, mr.errors):
    #   mr.viewed_user_auth.user_view.RevealEmail()

    page_data = {
        'user_tab_mode': 'st5',
        'viewing_user_page': ezt.boolean(True),
        'user_updates_tab_mode': self._TAB_MODE,
        }

    user_ids = self._GetUserIDsForUpdates(mr)
    project_ids = self._GetProjectIDsForUpdates(mr)
    page_data.update(activities.GatherUpdatesData(
        self.services, mr, user_ids=user_ids,
        project_ids=project_ids, ending=self._ENDING,
        updates_page_url=self._UPDATES_PAGE_URL, highlight=self._HIGHLIGHT))

    return page_data

  def _GetUserIDsForUpdates(self, _mr):
    """Returns a list of user IDs to retrieve activities from."""
    return None  # Means any.

  def _GetProjectIDsForUpdates(self, _mr):
    """Returns a list of project IDs to retrieve activities from."""
    return None  # Means any.


class UserUpdatesProjects(AbstractUserUpdatesPage):
  """Shows a page of updates from projects starred by a user."""

  _UPDATES_FEED_URL = urls.USER_UPDATES_PROJECTS
  _UPDATES_PAGE_URL = urls.USER_UPDATES_PROJECTS
  _HIGHLIGHT = 'project'
  _ENDING = 'by_user'
  _TAB_MODE = 'st2'

  def _GetProjectIDsForUpdates(self, mr):
    """Returns a list of project IDs whom to retrieve activities from."""
    with work_env.WorkEnv(mr, self.services) as we:
      starred_projects = we.ListStarredProjects(
          viewed_user_id=mr.viewed_user_auth.user_id)
    return [project.project_id for project in starred_projects]


class UserUpdatesDevelopers(AbstractUserUpdatesPage):
  """Shows a page of updates from developers starred by a user."""

  _UPDATES_FEED_URL = urls.USER_UPDATES_DEVELOPERS
  _UPDATES_PAGE_URL = urls.USER_UPDATES_DEVELOPERS
  _HIGHLIGHT = 'user'
  _ENDING = 'in_project'
  _TAB_MODE = 'st3'

  def _GetUserIDsForUpdates(self, mr):
    """Returns a list of user IDs whom to retrieve activities from."""
    user_ids = self.services.user_star.LookupStarredItemIDs(
        mr.cnxn, mr.viewed_user_auth.user_id)
    logging.debug('StarredUsers: %r', user_ids)
    return user_ids


class UserUpdatesIndividual(AbstractUserUpdatesPage):
  """Shows a page of updates initiated by a user."""

  _UPDATES_FEED_URL = urls.USER_UPDATES_MINE + '/user'
  _UPDATES_PAGE_URL = urls.USER_UPDATES_MINE
  _HIGHLIGHT = 'project'
  _TAB_MODE = 'st1'

  def _GetUserIDsForUpdates(self, mr):
    """Returns a list of user IDs whom to retrieve activities from."""
    return [mr.viewed_user_auth.user_id]
