# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions and classes used when searching for projects."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from businesslogic import work_env
from framework import framework_helpers
from framework import paginate
from framework import permissions


DEFAULT_RESULTS_PER_PAGE = 100


class ProjectSearchPipeline(object):
  """Manage the process of project search, filter, fetch, and pagination."""

  def __init__(self, mr, services,
               default_results_per_page=DEFAULT_RESULTS_PER_PAGE):

    self.mr = mr
    self.services = services
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
    with self.mr.profiler.Phase('getting all projects'):
      project_dict = self.services.project.GetProjects(
          cnxn, self.allowed_project_ids)
      project_list = sorted(
          project_dict.values(),
          key=lambda p: p.project_name)
      logging.info('project_list is %r', project_list)

    url_params = [(name, self.mr.GetParam(name)) for name in
                  framework_helpers.RECOGNIZED_PARAMS]
    self.pagination = paginate.ArtifactPagination(
        project_list,
        self.mr.GetPositiveIntParam('num', self.default_results_per_page),
        self.mr.GetPositiveIntParam('start'), self.mr.project_name,
        list_page_url, url_params=url_params)
    self.visible_results = self.pagination.visible_results
