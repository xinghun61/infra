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

  Each API request is implemented with a one-line "Run" method that matches
  the method defined in the .proto file, and a Do* method that:
  does any request-specific validation, uses work_env to safely operate on
  business objects, and returns a response proto.
  """

  DESCRIPTION = issues_prpc_pb2.IssuesServiceDescription

  def CreateIssue(self, request, prpc_context, cnxn=None, auth=None):
    return self.Run(self.DoCreateIssue, request, prpc_context,
                    cnxn=cnxn, auth=auth)

  def DoCreateIssue(self, _mc, request):
    response = issue_objects_pb2.Issue()
    response.CopyFrom(request.issue)
    return response

  def GetIssue(self, request, prpc_context, cnxn=None, auth=None):
    return self.Run(self.DoGetIssue, request, prpc_context,
                    cnxn=cnxn, auth=auth)

  def DoGetIssue(self, _mc, request):
    response = issues_pb2.IssueResponse()

    issue = issue_objects_pb2.Issue(
        project_name=request.issue_ref.project_name,
        local_id=request.issue_ref.local_id,
        summary='TODO: get issue from the database')
    response.issue.CopyFrom(issue)
    return response

  def DeleteIssueComment(self, request, prpc_context, cnxn=None, auth=None):
    return self.Run(self.DoDeleteIssueComment, request, prpc_context,
                    cnxn=cnxn, auth=auth)

  def DoDeleteIssueComment(self, _mc, _request):
    return empty_pb2.Empty()
