# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions used in sitewide servlets."""

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


def GetUserProjects(
    cnxn, services, user, effective_ids, viewed_user_effective_ids):
  """Get the projects to display in the user's profile.

  Args:
    cnxn: connection to the SQL database.
    services: An instance of services
    user: The user doing the viewing.
    effective_ids: set of int user IDs of the user viewing the projects
        (including any user group IDs).
    viewed_user_effective_ids: set of int user IDs of the user being viewed.

  Returns:
    A 4-tuple of lists of PBs:
      - live projects the viewed user owns
      - archived projects the viewed user owns
      - live projects the viewed user is a member of
      - live projects the viewed user is a contributor to

    Any projects the viewing user should not be able to see are filtered out.
    Admins can see everything, while other users can see all non-locked
    projects they own or are a member of, as well as all live projects.
  """
  (owned_project_ids, membered_project_ids,
   contrib_project_ids) = services.project.GetUserRolesInAllProjects(
       cnxn, viewed_user_effective_ids)

  # Each project should only be considered for at most one role category.
  # We keep the highest ranking roles and discard lower-ranking ones.
  membered_project_ids.difference_update(owned_project_ids)
  contrib_project_ids.difference_update(owned_project_ids)
  contrib_project_ids.difference_update(membered_project_ids)

  # Build a dictionary of (project_id -> project)
  # so that we can check permissions.
  combined = owned_project_ids.union(membered_project_ids).union(
      contrib_project_ids)
  projects_dict = services.project.GetProjects(cnxn, combined)
  projects_dict = _FilterProjectDict(user, effective_ids, projects_dict)

  visible_ownership = _PickProjects(owned_project_ids, projects_dict)
  visible_archived = _PickProjects(
      owned_project_ids, projects_dict, archived=True)
  visible_membership = _PickProjects(membered_project_ids, projects_dict)
  visible_contrib = _PickProjects(contrib_project_ids, projects_dict)

  return (_SortProjects(visible_ownership), _SortProjects(visible_archived),
          _SortProjects(visible_membership), _SortProjects(visible_contrib))


def _SortProjects(projects):
  return sorted(projects, key=lambda p: p.project_name)


def _PickProjects(project_ids, projects_dict, archived=False):
  """Select the projects named in project_ids from a preloaded dictionary.

  Args:
    project_ids: list of project_ids for the desired projects.
    projects_dict: dict {project_id: ProjectPB, ...} of a lot
        of preloaded projects, including all the desired ones that exist.
    archived: set to True if you want to return projects that are in a
        ARCHIVED state instead of those that are not.

  Returns:
    A list of Project PBs for the desired projects.  If one of them is
    not found in projects_dict, it is ignored.
  """
  # Done in 3 steps: lookup all existing requested projects, filter out
  # DELETABLE ones, then filter out ARCHIVED or non-ARCHIVED.
  results = [projects_dict.get(pid) for pid in project_ids
             if pid in projects_dict]
  results = [proj for proj in results
             if proj.state != project_pb2.ProjectState.DELETABLE]
  results = [proj for proj in results
             if archived == (proj.state == project_pb2.ProjectState.ARCHIVED)]
  return results


def _FilterProjectDict(user, effective_ids, projects_dict):
  """Return a new project dictionary which contains only viewable projects."""
  return {
      pid: project
      for pid, project in projects_dict.iteritems()
      if permissions.UserCanViewProject(user, effective_ids, project)
      }
