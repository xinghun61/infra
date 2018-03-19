# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from api.proto import issues_pb2
from api.proto import issues_prpc_pb2


class IssuesServicer(object):
  """Handle API requests related to Issue objects.
  """

  DESCRIPTION = issues_prpc_pb2.IssuesServiceDescription

  def CreateIssue(self, request, _context):
    assert isinstance(request, issues_pb2.CreateIssueRequest)
    assert request.project_name
    assert request.issue
    ret = issues_pb2.Issue()
    ret.CopyFrom(request.issue)
    return ret

  def DeleteIssueComment(self, request, _context):
    assert isinstance(request, issues_pb2.DeleteIssueCommentRequest)
    assert request.project_name
    assert request.local_id
    assert request.comment_id
    ret = issues_pb2.Comment(deleted=True)
    return ret
