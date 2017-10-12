# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display the hosting home page."""

import logging
from third_party import ezt

import settings
from businesslogic import work_env
from framework import permissions
from framework import servlet
from framework import template_helpers
from framework import urls
from project import project_views
from sitewide import projectsearch
from sitewide import sitewide_helpers


class HostingHome(servlet.Servlet):
  """HostingHome shows the Monorail site homepage and link to create a project.

  This needs to be a full Servlet rather than just a static page
  because we need to check permissions before offering the link to create
  a project.
  """

  _PAGE_TEMPLATE = 'sitewide/hosting-home-page.ezt'

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    can_create_project = permissions.CanCreateProject(mr.perms)

    # Kick off the search pipeline, it has its own promises for parallelism.
    pipeline = projectsearch.ProjectSearchPipeline(
        mr, self.services, self.profiler)

    # Meanwhile, determine which projects the signed-in user has starred.
    with work_env.WorkEnv(mr, self.services) as we:
      starred_projects = we.ListStarredProjects()
      starred_project_ids = {p.project_id for p in starred_projects}

    # A dict of project id to the user's membership status.
    project_memberships = {}
    if mr.auth.user_id:
      owned, _archive_owned, member_of, contrib_of = (
          sitewide_helpers.GetUserProjects(
              mr.cnxn, self.services, mr.auth.user_pb, mr.auth.effective_ids,
              mr.auth.effective_ids))
      project_memberships.update({proj.project_id: 'Owner' for proj in owned})
      project_memberships.update(
          {proj.project_id: 'Member' for proj in member_of})
      project_memberships.update(
          {proj.project_id: 'Contributor' for proj in contrib_of})

    # Finish the project search pipeline.
    pipeline.SearchForIDs()
    pipeline.GetProjectsAndPaginate(mr.cnxn, urls.HOSTING_HOME)
    project_ids = [p.project_id for p in pipeline.visible_results]
    star_count_dict = self.services.project_star.CountItemsStars(
        mr.cnxn, project_ids)

    # Make ProjectView objects
    project_view_list = [
        project_views.ProjectView(
            p, starred=p.project_id in starred_project_ids,
            num_stars=star_count_dict.get(p.project_id),
            membership_desc=project_memberships.get(p.project_id))
        for p in pipeline.visible_results]
    return {
        'can_create_project': ezt.boolean(can_create_project),
        'learn_more_link': settings.learn_more_link,
        'projects': project_view_list,
        'pagination': pipeline.pagination,
        }
