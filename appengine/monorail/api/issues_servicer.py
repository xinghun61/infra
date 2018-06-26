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
from framework import exceptions
from framework import framework_views
from proto import tracker_pb2
from tracker import tracker_bizobj


class IssuesServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Issue objects.

  Each API request is implemented with a method as defined in the
  .proto file that does any request-specific validation, uses work_env
  to safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = issues_prpc_pb2.IssuesServiceDescription

  def _GetProjectIssueAndConfig(self, mc, request, use_cache=True):
    """Get three objects that we need for most requests with an issue_ref."""
    with work_env.WorkEnv(mc, self.services, phase='getting P, I, C') as we:
      project = we.GetProjectByName(
          request.issue_ref.project_name, use_cache=use_cache)
      mc.LookupLoggedInUserPerms(project)
      config = we.GetProjectConfig(project.project_id, use_cache=use_cache)
      issue = we.GetIssueByLocalID(
        project.project_id, request.issue_ref.local_id, use_cache=use_cache)
    return project, issue, config

  @monorail_servicer.PRPCMethod
  def CreateIssue(self, _mc, request):
    response = issue_objects_pb2.Issue()
    response.CopyFrom(request.issue)
    return response

  @monorail_servicer.PRPCMethod
  def GetIssue(self, mc, request):
    """Return the specified issue in a response proto."""
    project, issue, config = self._GetProjectIssueAndConfig(mc, request)
    with work_env.WorkEnv(mc, self.services) as we:
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
  def UpdateIssue(self, mc, request):
    """Apply a delta and comment to the specified issue, then return it."""
    project, issue, config = self._GetProjectIssueAndConfig(
        mc, request, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      if request.HasField('delta'):
        delta = converters.IngestIssueDelta(
            mc.cnxn, self.services, request.delta, config)
      else:
        delta = tracker_pb2.IssueDelta()  # No changes specified.
      we.UpdateIssue(
          issue, delta, request.comment_content, send_email=request.send_email)
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
  def StarIssue(self, mc, request):
    """Star (or unstar) the specified issue."""
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      we.StarIssue(issue, request.starred)
      # Reload the issue to get the new star count.
      issue = we.GetIssue(issue.issue_id)

    with mc.profiler.Phase('converting to response objects'):
      response = issues_pb2.StarIssueResponse()
      response.star_count = issue.star_count

    return response

  @monorail_servicer.PRPCMethod
  def IsIssueStarred(self, mc, request):
    """Respond true if the signed-in user has starred the specified issue."""
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      is_starred = we.IsIssueStarred(issue)

    with mc.profiler.Phase('converting to response objects'):
      response = issues_pb2.IsIssueStarredResponse()
      response.is_starred = is_starred

    return response

  @monorail_servicer.PRPCMethod
  def ListComments(self, mc, request):
    """Return comments on the specified issue in a response proto."""
    project, issue, config = self._GetProjectIssueAndConfig(mc, request)
    with work_env.WorkEnv(mc, self.services) as we:
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
  def DeleteComment(self, mc, request):
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request, use_cache=False)
    with work_env.WorkEnv(mc, self.services) as we:
      all_comments = we.ListIssueComments(issue)
      try:
        comment = all_comments[request.sequence_num]
      except IndexError:
        raise exceptions.NoSuchCommentException()
      we.DeleteComment(issue, comment, request.delete)

    return empty_pb2.Empty()

  @monorail_servicer.PRPCMethod
  def UpdateApproval(self, mc, request):
    """Update an approval and return the updated approval in a reponse proto."""
    project, issue, config = self._GetProjectIssueAndConfig(
        mc, request, use_cache=False)
    with work_env.WorkEnv(mc, self.services) as we:
      approval_fd = tracker_bizobj.FindFieldDef(
          request.field_ref.field_name, config)
      # TODO(jojwang): monorail:3895, check approval_fd was actually found.

      approval_delta = converters.IngestApprovalDelta(
          mc.cnxn, self.services.user, request.approval_delta,
          mc.auth.user_id, config)

    with mc.profiler.Phase('updating approval'):
      av, _comment = we.UpdateIssueApproval(
          issue.issue_id, approval_fd.field_id,
          approval_delta, request.comment_content)

    # TODO(jojwang): monorail:3895, add comment to reponse.
    with mc.profiler.Phase('converting to response objects'):
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, av.approver_ids, [av.setter_id])
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)
      response = issues_pb2.UpdateApprovalResponse()
      response.approval.CopyFrom(converters.ConvertApproval(
          av, users_by_id, config))

    return response
