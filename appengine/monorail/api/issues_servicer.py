# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from api import monorail_servicer
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
    response = issues_pb2.Issue()
    response.CopyFrom(request.issue)
    return response

  def DeleteIssueComment(self, request, prpc_context, cnxn=None, auth=None):
    return self.Run(self.DoDeleteIssueComment, request, prpc_context,
                    cnxn=cnxn, auth=auth)

  def DoDeleteIssueComment(self, _mc, _request):
    return issues_pb2.Comment(deleted=True)
