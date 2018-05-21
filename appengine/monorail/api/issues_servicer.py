# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from google.protobuf import empty_pb2

from api import monorail_servicer
from api.api_proto import issue_objects_pb2
from api.api_proto import issues_pb2
from api.api_proto import issues_prpc_pb2


class IssuesServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Issue objects.

  Each API request is implemented with a method as defined in the
  .proto file that does any request-specific validation, uses work_env
  to safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = issues_prpc_pb2.IssuesServiceDescription

  @monorail_servicer.PRPCMethod
  def CreateIssue(self, _mc, request):
    response = issue_objects_pb2.Issue()
    response.CopyFrom(request.issue)
    return response

  @monorail_servicer.PRPCMethod
  def GetIssue(self, _mc, request):
    response = issues_pb2.IssueResponse()

    issue = issue_objects_pb2.Issue(
        project_name=request.issue_ref.project_name,
        local_id=request.issue_ref.local_id,
        summary='TODO: get issue from the database')
    response.issue.CopyFrom(issue)
    return response

  @monorail_servicer.PRPCMethod
  def DeleteIssueComment(self, _mc, _request):
    return empty_pb2.Empty()
