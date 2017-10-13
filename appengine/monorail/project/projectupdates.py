# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display a paginated list of activity stream updates."""

import logging

from third_party import ezt

from features import activities
from framework import servlet
from framework import urls


class ProjectUpdates(servlet.Servlet):
  """ProjectUpdates page shows a list of past activities."""

  _PAGE_TEMPLATE = 'project/project-updates-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_UPDATES

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""

    page_data = self._GatherUpdates(mr)
    page_data['subtab_mode'] = None
    page_data['user_updates_tab_mode'] = None
    logging.info('project updates data is %r', page_data)
    return page_data

  def _GatherUpdates(self, mr):
    """Gathers and returns activity streams data."""

    url = '/p/%s%s' % (mr.project_name, urls.UPDATES_LIST)
    return activities.GatherUpdatesData(
        self.services, mr, project_ids=[mr.project_id],
        ending='by_user', updates_page_url=url,
        autolink=self.services.autolink)
