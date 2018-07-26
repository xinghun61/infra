# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import logging

from api import monorail_servicer
from api import converters
from api.api_proto import projects_pb2
from api.api_proto import project_objects_pb2
from api.api_proto import projects_prpc_pb2
from businesslogic import work_env
from framework import framework_views
from framework import permissions
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers


class ProjectsServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Project objects.

  Each API request is implemented with a method as defined in the .proto
  file that does any request-specific validation, uses work_env to
  safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = projects_prpc_pb2.ProjectsServiceDescription

  def _GetProject(self, mc, request, use_cache=True):
    """Get the project object specified in the request."""
    with work_env.WorkEnv(mc, self.services, phase='getting project') as we:
      project = we.GetProjectByName(request.project_name, use_cache=use_cache)
      # Perms in this project are already looked up in MonorailServicer.
    return project

  @monorail_servicer.PRPCMethod
  def ListProjects(self, _mc, _request):
    return projects_pb2.ListProjectsResponse(
        projects=[
            project_objects_pb2.Project(name='One'),
            project_objects_pb2.Project(name='Two')],
        next_page_token='next...')

  @monorail_servicer.PRPCMethod
  def GetConfig(self, mc, request):
    """Return the specified project config."""
    project = self._GetProject(mc, request)

    with work_env.WorkEnv(mc, self.services) as we:
      config = we.GetProjectConfig(project.project_id)

    with mc.profiler.Phase('making user views'):
      users_involved = tracker_bizobj.UsersInvolvedInConfig(config)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)
      label_ids = tracker_bizobj.LabelIDsInvolvedInConfig(config)
      labels_by_id = {
        label_id: self.services.config.LookupLabel(
            mc.cnxn, config.project_id, label_id)
        for label_id in label_ids}

    result = converters.ConvertConfig(
        project, config, users_by_id, labels_by_id)
    return result

  @monorail_servicer.PRPCMethod
  def GetCustomPermissions(self, mc, request):
    """Return the custom permissions for the given project."""
    project = self._GetProject(mc, request)
    custom_permissions = permissions.GetCustomPermissions(project)

    result = projects_pb2.GetCustomPermissionsResponse(
        permissions=custom_permissions)
    return result

  @monorail_servicer.PRPCMethod
  def GetVisibleMembers(self, mc, request):
    """Return the members of the project that the user can see."""
    project = self._GetProject(mc, request)

    users_by_id = tracker_helpers.GetVisibleMembers(mc, project, self.services)

    user_refs = converters.ConvertUserRefs(sorted(users_by_id), [], users_by_id)
    group_refs = converters.ConvertUserRefs(
        sorted(uv.user_id for uv in users_by_id.values() if uv.is_group), [],
        users_by_id)

    result = projects_pb2.GetVisibleMembersResponse(
        user_refs=user_refs, group_refs=group_refs)
    return result

  @monorail_servicer.PRPCMethod
  def GetFieldOptions(self, mc, request):
    """Return the possible users for each user field that needs permissions."""
    project = self._GetProject(mc, request)

    with work_env.WorkEnv(mc, self.services) as we:
      config = we.GetProjectConfig(project.project_id)

    users_by_id = tracker_helpers.GetVisibleMembers(mc, project, self.services)

    field_options = []
    for fd in config.field_defs:
      if fd.needs_perm and not fd.is_deleted:
        qualified_users = field_helpers.FilterValidFieldValues(
            mc, project, self.services, fd, users_by_id.values())
        field_options.append(converters.ConvertFieldOptions(
            fd, [uv.user_id for uv in qualified_users], users_by_id, config))

    result = projects_pb2.GetFieldOptionsResponse(field_options=field_options)
    return result
