# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display the project summary page."""

import logging

from framework import framework_bizobj
from framework import permissions
from framework import servlet
from project import project_views

from third_party import markdown


class ProjectSummary(servlet.Servlet):
  """Page to show brief project description and process documentation."""

  _PAGE_TEMPLATE = 'project/project-summary-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""

    with mr.profiler.Phase('getting project star count'):
      num_stars = self.services.project_star.CountItemStars(
          mr.cnxn, mr.project_id)
      plural = '' if num_stars == 1 else 's'

    page_data = {
        'admin_tab_mode': self.PROCESS_TAB_SUMMARY,
        'formatted_project_description':
            markdown.Markdown(mr.project.description),
        'access_level': project_views.ProjectAccessView(mr.project.access),
        'num_stars': num_stars,
        'plural': plural,
        'home_page': mr.project.home_page,
        'docs_url': mr.project.docs_url,
        'source_url': mr.project.source_url,
        }

    return page_data

  def GatherHelpData(self, mr, page_data):
    """Return a dict of values to drive on-page user help.

    Args:
      mr: common information parsed from the HTTP request.
      page_data: Dictionary of base and page template data.

    Returns:
      A dict of values to drive on-page user help, to be added to page_data.
    """
    help_data = super(ProjectSummary, self).GatherHelpData(mr, page_data)
    dismissed = mr.auth.user_pb.dismissed_cues
    project = mr.project

    # Cue cards for project owners.
    if self.CheckPerm(mr, permissions.EDIT_PROJECT):
      if ('document_team_duties' not in dismissed
            and len(framework_bizobj.AllProjectMembers(project)) > 1
            and not self.services.project.GetProjectCommitments(
                mr.cnxn, mr.project_id).commitments):
        help_data['cue'] = 'document_team_duties'

    return help_data
