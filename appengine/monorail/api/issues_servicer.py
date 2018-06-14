# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import logging

from google.protobuf import empty_pb2

from api import monorail_servicer
from api import converters
from api.api_proto import issue_objects_pb2
from api.api_proto import issues_pb2
from api.api_proto import issues_prpc_pb2
from businesslogic import work_env
from framework import framework_views
from tracker import tracker_bizobj


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
  def GetIssue(self, mc, request):
    """Return the specified issue in a response proto."""
    with work_env.WorkEnv(mc, self.services) as we:
      project = we.GetProjectByName(request.issue_ref.project_name)
      mc.LookupLoggedInUserPerms(project)
      config = we.GetProjectConfig(project.project_id)
      issue = we.GetIssueByLocalID(
        project.project_id, request.issue_ref.local_id)
      related_refs = we.GetRelatedIssueRefs(issue)

    with mc.profiler.Phase('making user views'):
      users_involved_in_issue = tracker_bizobj.UsersInvolvedInIssues([issue])
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved_in_issue)
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)

    with mc.profiler.Phase('converting to response objects'):
      response = issues_pb2.IssueResponse()
      response.issue.CopyFrom(converters.ConvertIssue(
          issue, users_by_id, related_refs, config))

    return response

  @monorail_servicer.PRPCMethod
  def ListComments(self, mc, request):
    """Return comments on the specified issue in a response proto."""
    with work_env.WorkEnv(mc, self.services) as we:
      project = we.GetProjectByName(request.issue_ref.project_name)
      config = we.GetProjectConfig(project.project_id)
      mc.LookupLoggedInUserPerms(project)

    with work_env.WorkEnv(mc, self.services) as we:
      issue = we.GetIssueByLocalID(
          project.project_id, request.issue_ref.local_id)
      comments = we.ListIssueComments(issue)

    with mc.profiler.Phase('making user views'):
      users_involved_in_comments = tracker_bizobj.UsersInvolvedInCommentList(
         comments)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved_in_comments)
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)

    with mc.profiler.Phase('converting to response objects'):
      converted_comments = converters.ConvertCommentList(
          issue, comments, users_by_id, config, mc.auth.user_id)
      response = issues_pb2.ListCommentsResponse(comments=converted_comments)

    return response

  @monorail_servicer.PRPCMethod
  def DeleteIssueComment(self, _mc, _request):
    return empty_pb2.Empty()
