# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from api import monorail_servicer
from api.api_proto import projects_pb2
from api.api_proto import projects_prpc_pb2


class ProjectsServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Project objects.

  Each API request is implemented with a one-line "Run" method that matches
  the method defined in the .proto file, and a Do* method that:
  does any request-specific validation, uses work_env to safely operate on
  business objects, and returns a response proto.
  """

  DESCRIPTION = projects_prpc_pb2.ProjectsServiceDescription

  def ListProjects(self, request, prpc_context, cnxn=None, auth=None):
    return self.Run(self.DoListProjects, request, prpc_context,
                    cnxn=cnxn, auth=auth)

  def DoListProjects(self, _mc, _request):
    return projects_pb2.ListProjectsResponse(
        projects=[
            projects_pb2.Project(name='One'),
            projects_pb2.Project(name='Two')],
        next_page_token='next...')

  def UpdateProjectConfiguredLabels(
      self, request, prpc_context, cnxn=None, auth=None):
    return self.Run(self.DoUpdateProjectConfiguredLabels, request, prpc_context,
                    cnxn=cnxn, auth=auth)

  def DoUpdateProjectConfiguredLabels(self, _mc, _request):
    return projects_pb2.Labels(
        labels=[
            projects_pb2.Label(name='Priority-Critical', rank=1),
            projects_pb2.Label(name='Priority-High', rank=2),
            projects_pb2.Label(name='Priority-Medium', rank=3),
            projects_pb2.Label(name='Priority-Low', rank=4)])

  def PatchProjectConfiguredLabels(
      self, request, prpc_context, cnxn=None, auth=None):
    return self.Run(self.DoPatchProjectConfiguredLabels, request, prpc_context,
                    cnxn=cnxn, auth=auth)

  def DoPatchProjectConfiguredLabels(self, _mc, _request):
    return projects_pb2.Labels(
        labels=[
            projects_pb2.Label(name='Priority-Critical', rank=1),
            projects_pb2.Label(name='Priority-High', rank=2),
            projects_pb2.Label(name='Priority-Medium', rank=3),
            projects_pb2.Label(name='Priority-Low', rank=4)])
