# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from api.proto import projects_pb2
from api.proto import projects_prpc_pb2


class ProjectsServicer(object):
  """Handle API requests related to Project objects.
  """

  DESCRIPTION = projects_prpc_pb2.ProjectsServiceDescription

  def ListProjects(self, request, _context):
    assert isinstance(request, projects_pb2.ListProjectsRequest)
    ret = projects_pb2.ListProjectsResponse()
    # Return example data for now
    ret.projects.extend([
        projects_pb2.Project(name='One'),
        projects_pb2.Project(name='Two')])
    ret.next_page_token = 'next...'
    return ret

  def UpdateProjectConfiguredLabels(self, request, _context):
    assert isinstance(
        request, projects_pb2.UpdateProjectConfiguredLabelsRequest)
    assert request.project
    ret = projects_pb2.Labels()
    # Return example data for now
    ret.labels.extend([
        projects_pb2.Label(name='Priority-Critical', rank=1),
        projects_pb2.Label(name='Priority-High', rank=2),
        projects_pb2.Label(name='Priority-Medium', rank=3),
        projects_pb2.Label(name='Priority-Low', rank=4)])
    return ret

  def PatchProjectConfiguredLabels(self, request, _context):
    assert isinstance(
        request, projects_pb2.PatchProjectConfiguredLabelsRequest)
    assert request.project
    ret = projects_pb2.Labels()
    # Return example data for now
    ret.labels.extend([
        projects_pb2.Label(name='Priority-Critical', rank=1),
        projects_pb2.Label(name='Priority-High', rank=2),
        projects_pb2.Label(name='Priority-Medium', rank=3),
        projects_pb2.Label(name='Priority-Low', rank=4)])
    return ret
