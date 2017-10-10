# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions and classes used when searching for projects."""

import logging

from businesslogic import work_env
from framework import framework_helpers
from framework import paginate
from framework import permissions


DEFAULT_RESULTS_PER_PAGE = 100


class ProjectSearchPipeline(object):
  """Manage the process of project search, filter, fetch, and pagination."""

  def __init__(self, mr, services, prof,
               default_results_per_page=DEFAULT_RESULTS_PER_PAGE):

    self.mr = mr
    self.services = services
    self.profiler = prof
    self.default_results_per_page = default_results_per_page
    self.pagination = None
    self.allowed_project_ids = None
    self.visible_results = None

  def SearchForIDs(self):
    """Get project IDs the user has permission to view."""
    with work_env.WorkEnv(self.mr, self.services) as we:
      self.allowed_project_ids = we.ListProjects()
      logging.info('allowed_project_ids is %r', self.allowed_project_ids)

  def GetProjectsAndPaginate(self, cnxn, list_page_url):
    """Paginate the filtered list of project names and retrieve Project PBs.

    Args:
      cnxn: connection to SQL database.
      list_page_url: string page URL for prev and next links.
    """
    self.pagination = paginate.ArtifactPagination(
        self.mr, self.allowed_project_ids, self.default_results_per_page,
        list_page_url)
    with self.profiler.Phase('getting projects on current pagination page'):
      project_dict = self.services.project.GetProjects(
          cnxn, self.pagination.visible_results)
      self.visible_results = [
          project_dict[pid] for pid in self.pagination.visible_results]
      logging.info('visible_results is %r', self.visible_results)
