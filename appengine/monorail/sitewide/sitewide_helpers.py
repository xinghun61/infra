# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions used in sitewide servlets."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from framework import permissions
from proto import project_pb2


def GetViewableStarredProjects(
    cnxn, services, viewed_user_id, effective_ids, logged_in_user):
  """Returns a list of viewable starred projects."""
  starred_project_ids = services.project_star.LookupStarredItemIDs(
      cnxn, viewed_user_id)
  projects = services.project.GetProjects(cnxn, starred_project_ids).values()
  viewable_projects = FilterViewableProjects(
      projects, logged_in_user, effective_ids)
  return viewable_projects


def FilterViewableProjects(project_list, logged_in_user, effective_ids):
  """Return subset of LIVE project protobufs viewable by the given user."""
  viewable_projects = []
  for project in project_list:
    if (project.state == project_pb2.ProjectState.LIVE and
        permissions.UserCanViewProject(
            logged_in_user, effective_ids, project)):
      viewable_projects.append(project)

  return viewable_projects
