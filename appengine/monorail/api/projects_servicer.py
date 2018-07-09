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


class ProjectsServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Project objects.

  Each API request is implemented a method as defined in the .proto
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

    result = converters.ConvertConfig(
        mc.cnxn, self.services.user, project, config)
    return result

