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
from features import filterrules_helpers
from features import savedqueries_helpers
from framework import exceptions
from framework import framework_views
from proto import tracker_pb2
from search import searchpipeline
from tracker import tracker_bizobj
from tracker import tracker_helpers


class IssuesServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Issue objects.

  Each API request is implemented with a method as defined in the
  .proto file that does any request-specific validation, uses work_env
  to safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = issues_prpc_pb2.IssuesServiceDescription

  def _GetProjectIssueAndConfig(self, mc, request, use_cache=True,
                                issue_required=True):
    """Get three objects that we need for most requests with an issue_ref."""
    issue = None
    with work_env.WorkEnv(mc, self.services, phase='getting P, I, C') as we:
      project = we.GetProjectByName(
          request.issue_ref.project_name, use_cache=use_cache)
      mc.LookupLoggedInUserPerms(project)
      config = we.GetProjectConfig(project.project_id, use_cache=use_cache)
      if issue_required or request.issue_ref.local_id:
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
  def ListReferencedIssues(self, mc, request):
    """Return the specified issues in a response proto."""
    if not request.issue_refs:
      return issues_pb2.ListReferencedIssuesResponse()

    for issue_ref in request.issue_refs:
      if not issue_ref.project_name:
        raise exceptions.InputException('Param `project_name` required.')
      if not issue_ref.local_id:
        raise exceptions.InputException('Param `local_id` required.')

    default_project_name = request.issue_refs[0].project_name
    ref_tuples = [
        (ref.project_name, ref.local_id) for ref in request.issue_refs]
    with work_env.WorkEnv(mc, self.services) as we:
      open_issues, closed_issues = we.ListReferencedIssues(
          ref_tuples, default_project_name)

    # TODO(jojwang): monorail:4033, add issue summary, by replacing IssueRef
    # protoc objects with Issue protoc objects.
    with mc.profiler.Phase('converting to response objects'):
      open_refs = [converters.ConvertIssueRef(
          (issue.project_name, issue.local_id)) for issue in open_issues]
      closed_refs = [converters.ConvertIssueRef(
          (issue.project_name, issue.local_id)) for issue in closed_issues]
      response = issues_pb2.ListReferencedIssuesResponse(
          open_refs=open_refs, closed_refs=closed_refs)

    return response

  @monorail_servicer.PRPCMethod
  def UpdateIssue(self, mc, request):
    """Apply a delta and comment to the specified issue, then return it."""
    project, issue, config = self._GetProjectIssueAndConfig(
        mc, request, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      if request.HasField('delta'):
        delta = converters.IngestIssueDelta(
            mc.cnxn, self.services, request.delta, config, issue.phases)
      else:
        delta = tracker_pb2.IssueDelta()  # No changes specified.
      attachments = converters.IngestAttachmentUploads(request.uploads)
      we.UpdateIssue(
          issue, delta, request.comment_content, send_email=request.send_email,
          attachments=attachments, is_description=request.is_description)
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
  def ListActivities(self, mc, request):
    """Return issue activities by a specified user in a response proto."""
    converted_user = converters.IngestUserRefs(mc.cnxn,[request.user_ref],
        self.services.user)[0]
    user = self.services.user.GetUser(mc.cnxn, converted_user)
    comments = self.services.issue.GetIssueActivity(
        mc.cnxn, user_ids={request.user_ref.user_id})
    issues = self.services.issue.GetIssues(
        mc.cnxn, {c.issue_id for c in comments})
    project_dict = tracker_helpers.GetAllIssueProjects(
        mc.cnxn, issues, self.services.project)
    config_dict = self.services.config.GetProjectConfigs(
        mc.cnxn, project_dict.keys())
    allowed_issues = tracker_helpers.FilterOutNonViewableIssues(
        mc.auth.effective_ids, user, project_dict,
        config_dict, issues)
    issue_dict = {issue.issue_id: issue for issue in allowed_issues}
    comments = [
        c for c in comments if c.issue_id in issue_dict]
    users_by_id = framework_views.MakeAllUserViews(
        mc.cnxn, self.services.user, [request.user_ref.user_id])
    for project in project_dict.values():
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)

    with mc.profiler.Phase('converting to response objects'):
      converted_comments = []
      for c in comments:
        issue = issue_dict.get(c.issue_id)
        result = converters.ConvertComment(
            issue, c,
            users_by_id,
            config_dict.get(issue.project_id),
            {c.id: 1} if c.is_description else {},
            mc.auth.user_id)
        converted_comments.append(result)
      converted_issues = [issue_objects_pb2.IssueSummary(
          project_name=issue.project_name, local_id=issue.local_id,
          summary=issue.summary) for issue in allowed_issues]
      response = issues_pb2.ListActivitiesResponse(
          comments=converted_comments, issue_summaries=converted_issues)

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
      if not approval_fd:
        raise exceptions.NoSuchFieldDefException()
      if request.HasField('approval_delta'):
        approval_delta = converters.IngestApprovalDelta(
            mc.cnxn, self.services.user, request.approval_delta,
            mc.auth.user_id, config)
      else:
        approval_delta = tracker_pb2.IssueApprovalDelta()
      attachments = converters.IngestAttachmentUploads(request.uploads)

    with mc.profiler.Phase('updating approval'):
      av, _comment = we.UpdateIssueApproval(
          issue.issue_id, approval_fd.field_id, approval_delta,
          request.comment_content, request.is_description,
          attachments=attachments)

    with mc.profiler.Phase('converting to response objects'):
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, av.approver_ids, [av.setter_id])
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)
      response = issues_pb2.UpdateApprovalResponse()
      response.approval.CopyFrom(converters.ConvertApproval(
          av, users_by_id, config))

    return response

  @monorail_servicer.PRPCMethod
  def IssueSnapshot(self, mc, request):
    """Fetch IssueSnapshot counts for charting."""
    warnings = []

    if not request.timestamp:
      raise exceptions.InputException('Param `timestamp` required.')

    if not request.project_name:
      raise exceptions.InputException('Param `project_name` required.')

    if request.group_by == 'label' and not request.label_prefix:
      raise exceptions.InputException('Param `label_prefix` required.')

    if request.canned_query:
      canned_query = savedqueries_helpers.SavedQueryIDToCond(
          mc.cnxn, self.services.features, request.canned_query)
      canned_query, warnings = searchpipeline.ReplaceKeywordsWithUserID(
          mc.auth.user_id, canned_query)
    else:
      canned_query = None

    with work_env.WorkEnv(mc, self.services) as we:
      project = we.GetProjectByName(request.project_name)
      results, unsupported_fields = we.SnapshotCountsQuery(
          project, request.timestamp, request.group_by, request.label_prefix,
          request.query, canned_query)

    snapshot_counts = [
      issues_pb2.IssueSnapshotCount(dimension=key, count=result)
      for key, result in results.iteritems()
    ]
    response = issues_pb2.IssueSnapshotResponse()
    response.snapshot_count.extend(snapshot_counts)
    response.unsupported_field.extend(unsupported_fields)
    response.unsupported_field.extend(warnings)
    return response

  @monorail_servicer.PRPCMethod
  def PresubmitIssue(self, mc, request):
    """Provide the UI with warnings and suggestions."""
    project, existing_issue, config = self._GetProjectIssueAndConfig(
        mc, request, issue_required=False)

    with mc.profiler.Phase('making user views'):
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, [request.issue_delta.owner_ref.user_id])
      proposed_owner_view = users_by_id[request.issue_delta.owner_ref.user_id]

    with mc.profiler.Phase('initializing proposed_issue'):
      issue_delta = converters.IngestIssueDelta(
          mc.cnxn, self.services, request.issue_delta, config, None)
      proposed_issue = tracker_pb2.Issue(
          project_id=project.project_id,
          local_id=request.issue_ref.local_id,
          summary=issue_delta.summary,
          status=issue_delta.status,
          owner_id=issue_delta.owner_id,
          labels=issue_delta.labels_add,
          component_ids=issue_delta.comp_ids_add,
          project_name=project.project_name,
          field_values=issue_delta.field_vals_add)
      if existing_issue:
        proposed_issue.attachment_count = existing_issue.attachment_count
        proposed_issue.star_count = existing_issue.star_count

    with mc.profiler.Phase('applying rules'):
      _, traces = filterrules_helpers.ApplyFilterRules(
          mc.cnxn, self.services, proposed_issue, config)
      logging.info('proposed_issue is now: %r', proposed_issue)
      logging.info('traces are: %r', traces)

    with mc.profiler.Phase('making derived user views'):
      derived_users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, [proposed_issue.derived_owner_id],
          proposed_issue.derived_cc_ids)

    with mc.profiler.Phase('pair derived values with rule explanations'):
      (derived_labels, derived_owners, derived_ccs, warnings, errors) = (
          tracker_helpers.PairDerivedValuesWithRuleExplanations(
              proposed_issue, traces, derived_users_by_id))

    result = issues_pb2.PresubmitIssueResponse(
        owner_availability=proposed_owner_view.avail_message_short,
        owner_availability_state=proposed_owner_view.avail_state,
        derived_labels=converters.ConvertValueAndWhyList(derived_labels),
        derived_owners=converters.ConvertValueAndWhyList(derived_owners),
        derived_ccs=converters.ConvertValueAndWhyList(derived_ccs),
        warnings=converters.ConvertValueAndWhyList(warnings),
        errors=converters.ConvertValueAndWhyList(errors))
    return result
