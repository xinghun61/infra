# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import copy
import logging

from google.protobuf import empty_pb2

import settings
from api import monorail_servicer
from api import converters
from api.api_proto import issue_objects_pb2
from api.api_proto import issues_pb2
from api.api_proto import issues_prpc_pb2
from businesslogic import work_env
from features import filterrules_helpers
from features import savedqueries_helpers
from framework import exceptions
from framework import framework_constants
from framework import framework_views
from framework import permissions
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

  def _GetProjectIssueAndConfig(
      self, mc, issue_ref, use_cache=True, issue_required=True,
      view_deleted=False):
    """Get three objects that we need for most requests with an issue_ref."""
    issue = None
    with work_env.WorkEnv(mc, self.services, phase='getting P, I, C') as we:
      project = we.GetProjectByName(
          issue_ref.project_name, use_cache=use_cache)
      mc.LookupLoggedInUserPerms(project)
      config = we.GetProjectConfig(project.project_id, use_cache=use_cache)
      if issue_required or issue_ref.local_id:
        try:
          issue = we.GetIssueByLocalID(
              project.project_id, issue_ref.local_id, use_cache=use_cache,
              allow_viewing_deleted=view_deleted)
        except exceptions.NoSuchIssueException as e:
          issue = None
          if issue_required:
            raise e
    return project, issue, config

  def _GetProjectIssueIDsAndConfig(
      self, mc, issue_refs, use_cache=True):
    """Get info from a single project for repeated issue_refs requests."""
    project_names = set()
    local_ids = []
    for issue_ref in issue_refs:
      if not issue_ref.local_id:
        raise exceptions.InputException('Param `local_id` required.')
      local_ids.append(issue_ref.local_id)
      if issue_ref.project_name:
        project_names.add(issue_ref.project_name)

    if not project_names:
      raise exceptions.InputException('Param `project_name` required.')
    if len(project_names) != 1:
      raise exceptions.InputException(
          'This method does not support cross-project issue_refs.')
    project_name = project_names.pop()
    with work_env.WorkEnv(mc, self.services, phase='getting P, I ids, C') as we:
      project = we.GetProjectByName(project_name, use_cache=use_cache)
      mc.LookupLoggedInUserPerms(project)
      config = we.GetProjectConfig(project.project_id, use_cache=use_cache)
      project_local_id_pairs = [(project.project_id, local_id)
                                for local_id in local_ids]
    issue_ids, _misses = self.services.issue.LookupIssueIDs(
        mc.cnxn, project_local_id_pairs)
    return project, issue_ids, config

  @monorail_servicer.PRPCMethod
  def CreateIssue(self, _mc, request):
    response = issue_objects_pb2.Issue()
    response.CopyFrom(request.issue)
    return response

  @monorail_servicer.PRPCMethod
  def GetIssue(self, mc, request):
    """Return the specified issue in a response proto."""
    issue_ref = request.issue_ref
    project, issue, config = self._GetProjectIssueAndConfig(
        mc, issue_ref, view_deleted=True, issue_required=False)

    # Code for getting where a moved issue was moved to.
    if issue is None:
      moved_to_ref = self.services.issue.GetCurrentLocationOfMovedIssue(
          mc.cnxn, project.project_id, issue_ref.local_id)
      moved_to_project_id, moved_to_id = moved_to_ref
      moved_to_project_name = None

      if moved_to_project_id is not None:
        with work_env.WorkEnv(mc, self.services) as we:
          moved_to_project = we.GetProject(moved_to_project_id)
          moved_to_project_name = moved_to_project.project_name
        return issues_pb2.IssueResponse(moved_to_ref=converters.ConvertIssueRef(
            (moved_to_project_name, moved_to_id)))

      raise exceptions.NoSuchIssueException()

    if issue.deleted:
      return issues_pb2.IssueResponse(
          issue=issue_objects_pb2.Issue(is_deleted=True))

    with work_env.WorkEnv(mc, self.services) as we:
      related_refs = we.GetRelatedIssueRefs([issue])

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
  def ListIssues(self, mc, request):
    """Return the list of issues for projects that satisfy the given query."""
    use_cached_searches = not settings.local_mode
    with work_env.WorkEnv(mc, self.services) as we:
      start, max_items = converters.IngestPagination(request.pagination)
      pipeline = we.ListIssues(
          request.query, request.project_names, mc.auth.user_id,
          max_items, start, [], request.canned_query or 1,
          request.group_by_spec, request.sort_spec, use_cached_searches)
    with mc.profiler.Phase('reveal emails to members'):
      projects = self.services.project.GetProjectsByName(
          mc.cnxn, request.project_names)
      for _, p in projects.items():
        framework_views.RevealAllEmailsToMembers(
            mc.auth, p, pipeline.users_by_id)

    converted_results = []
    with work_env.WorkEnv(mc, self.services) as we:
      for issue in pipeline.visible_results:
        related_refs = we.GetRelatedIssueRefs([issue])
        converted_results.append(
            converters.ConvertIssue(issue, pipeline.users_by_id, related_refs,
                                    pipeline.harmonized_config))
    return issues_pb2.ListIssuesResponse(
        issues=converted_results, total_results=pipeline.pagination.total_count)


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
      all_issues = open_issues + closed_issues
      all_project_ids = [issue.project_id for issue in all_issues]
      related_refs = we.GetRelatedIssueRefs(all_issues)
      configs = we.GetProjectConfigs(all_project_ids)

    with mc.profiler.Phase('making user views'):
      users_involved = tracker_bizobj.UsersInvolvedInIssues(all_issues)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, None, users_by_id)

    with mc.profiler.Phase('converting to response objects'):
      converted_open_issues = [
          converters.ConvertIssue(
              issue, users_by_id, related_refs, configs[issue.project_id])
          for issue in open_issues]
      converted_closed_issues = [
          converters.ConvertIssue(
              issue, users_by_id, related_refs, configs[issue.project_id])
          for issue in closed_issues]
      response = issues_pb2.ListReferencedIssuesResponse(
          open_refs=converted_open_issues, closed_refs=converted_closed_issues)

    return response

  @monorail_servicer.PRPCMethod
  def ListApplicableFieldDefs(self, mc, request):
    """Returns specified issues' applicable field refs in a response proto."""
    if not request.issue_refs:
      return issues_pb2.ListApplicableFieldDefsResponse()

    _project, issue_ids, config = self._GetProjectIssueIDsAndConfig(
        mc, request.issue_refs)
    with work_env.WorkEnv(mc, self.services) as we:
      fds = we.ListApplicableFieldDefs(issue_ids, config)

    users_by_id = {}
    with mc.profiler.Phase('converting to response objects'):
      users_involved = tracker_bizobj.UsersInvolvedInConfig(config)
      users_by_id.update(framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved))
      field_defs = [
          converters.ConvertFieldDef(fd, [], users_by_id, config, True)
          for fd in fds]

    return issues_pb2.ListApplicableFieldDefsResponse(field_defs=field_defs)

  @monorail_servicer.PRPCMethod
  def UpdateIssue(self, mc, request):
    """Apply a delta and comment to the specified issue, then return it."""
    project, issue, config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      if request.HasField('delta'):
        delta = converters.IngestIssueDelta(
            mc.cnxn, self.services, request.delta, config, issue.phases)
      else:
        delta = tracker_pb2.IssueDelta()  # No changes specified.
      attachments = converters.IngestAttachmentUploads(request.uploads)
      we.UpdateIssue(
          issue, delta, request.comment_content, send_email=request.send_email,
          attachments=attachments, is_description=request.is_description,
          kept_attachments=list(request.kept_attachments))
      related_refs = we.GetRelatedIssueRefs([issue])

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
        mc, request.issue_ref, use_cache=False)

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
        mc, request.issue_ref, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      is_starred = we.IsIssueStarred(issue)

    with mc.profiler.Phase('converting to response objects'):
      response = issues_pb2.IsIssueStarredResponse()
      response.is_starred = is_starred

    return response

  @monorail_servicer.PRPCMethod
  def ListStarredIssues(self, mc, _request):
    """Return a list of issue ids that the signed-in user has starred."""
    with work_env.WorkEnv(mc, self.services) as we:
      starred_issues = we.ListStarredIssueIDs()
      starred_issues_dict = we.GetIssueRefs(starred_issues)

    with mc.profiler.Phase('converting to response objects'):
      converted_starred_issue_refs = converters.ConvertIssueRefs(
        starred_issues, starred_issues_dict)
      response = issues_pb2.ListStarredIssuesResponse(
        starred_issue_refs=converted_starred_issue_refs)

    return response

  @monorail_servicer.PRPCMethod
  def ListComments(self, mc, request):
    """Return comments on the specified issue in a response proto."""
    project, issue, config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref)
    with work_env.WorkEnv(mc, self.services) as we:
      comments = we.ListIssueComments(issue)
      _, comment_reporters = we.LookupIssueFlaggers(issue)

    with mc.profiler.Phase('making user views'):
      users_involved_in_comments = tracker_bizobj.UsersInvolvedInCommentList(
         comments)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved_in_comments)
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)

    with mc.profiler.Phase('converting to response objects'):
      issue_perms = permissions.UpdateIssuePermissions(
          mc.perms, project, issue, mc.auth.effective_ids, config=config)
      converted_comments = converters.ConvertCommentList(
          issue, comments, config, users_by_id, comment_reporters,
          mc.auth.user_id, issue_perms)
      response = issues_pb2.ListCommentsResponse(comments=converted_comments)

    return response

  @monorail_servicer.PRPCMethod
  def ListActivities(self, mc, request):
    """Return issue activities by a specified user in a response proto."""
    converted_user = converters.IngestUserRef(mc.cnxn, request.user_ref,
        self.services.user)
    user = self.services.user.GetUser(mc.cnxn, converted_user)
    comments = self.services.issue.GetIssueActivity(
        mc.cnxn, user_ids={request.user_ref.user_id})
    issues = self.services.issue.GetIssues(
        mc.cnxn, {c.issue_id for c in comments})
    project_dict = tracker_helpers.GetAllIssueProjects(
        mc.cnxn, issues, self.services.project)
    config_dict = self.services.config.GetProjectConfigs(
        mc.cnxn, list(project_dict.keys()))
    allowed_issues = tracker_helpers.FilterOutNonViewableIssues(
        mc.auth.effective_ids, user, project_dict,
        config_dict, issues)
    issue_dict = {issue.issue_id: issue for issue in allowed_issues}
    comments = [
        c for c in comments if c.issue_id in issue_dict]

    users_by_id = framework_views.MakeAllUserViews(
        mc.cnxn, self.services.user, [request.user_ref.user_id],
        tracker_bizobj.UsersInvolvedInCommentList(comments))
    for project in project_dict.values():
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)

    issues_by_project = {}
    for issue in allowed_issues:
      issues_by_project.setdefault(issue.project_id, []).append(issue)

    # A dictionary {issue_id: perms} of the PermissionSet for the current user
    # on each of the issues.
    issue_perms_dict = {}
    # A dictionary {comment_id: [reporter_id]} of users who have reported the
    # comment as spam.
    comment_reporters = {}
    for project_id, project_issues in issues_by_project.items():
      mc.LookupLoggedInUserPerms(project_dict[project_id])
      issue_perms_dict.update({
          issue.issue_id: permissions.UpdateIssuePermissions(
              mc.perms, project_dict[issue.project_id], issue,
              mc.auth.effective_ids, config=config_dict[issue.project_id])
          for issue in project_issues})

      with work_env.WorkEnv(mc, self.services) as we:
        project_issue_reporters = we.LookupIssuesFlaggers(project_issues)
        for _, issue_comment_reporters in project_issue_reporters.values():
          comment_reporters.update(issue_comment_reporters)

    with mc.profiler.Phase('converting to response objects'):
      converted_comments = []
      for c in comments:
        issue = issue_dict.get(c.issue_id)
        issue_perms = issue_perms_dict.get(c.issue_id)
        result = converters.ConvertComment(
            issue, c,
            config_dict.get(issue.project_id),
            users_by_id,
            comment_reporters.get(c.id, []),
            {c.id: 1} if c.is_description else {},
            mc.auth.user_id, issue_perms)
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
        mc, request.issue_ref, use_cache=False)
    with work_env.WorkEnv(mc, self.services) as we:
      all_comments = we.ListIssueComments(issue)
      try:
        comment = all_comments[request.sequence_num]
      except IndexError:
        raise exceptions.NoSuchCommentException()
      we.DeleteComment(issue, comment, request.delete)

    return empty_pb2.Empty()

  @monorail_servicer.PRPCMethod
  def BulkUpdateApprovals(self, mc, request):
    """Update multiple issues' approval and return the updated issue_refs."""
    if not request.issue_refs:
      raise exceptions.InputException('Param `issue_refs` empty.')

    project, issue_ids, config = self._GetProjectIssueIDsAndConfig(
        mc, request.issue_refs)

    approval_fd = tracker_bizobj.FindFieldDef(
        request.field_ref.field_name, config)
    if not approval_fd:
      raise exceptions.NoSuchFieldDefException()
    if request.HasField('approval_delta'):
      approval_delta = converters.IngestApprovalDelta(
          mc.cnxn, self.services.user, request.approval_delta,
          mc.auth.user_id, config)
    else:
      approval_delta = tracker_pb2.ApprovalDelta()
    # No bulk adding approval attachments for now.

    with work_env.WorkEnv(mc, self.services, phase='updating approvals') as we:
      updated_issue_ids = we.BulkUpdateIssueApprovals(
          issue_ids, approval_fd.field_id, project, approval_delta,
          request.comment_content, send_email=request.send_email)
      with mc.profiler.Phase('converting to response objects'):
        issue_ref_pairs = we.GetIssueRefs(updated_issue_ids)
        issue_refs = [converters.ConvertIssueRef(pair)
                      for pair in issue_ref_pairs.values()]
        response = issues_pb2.BulkUpdateApprovalsResponse(issue_refs=issue_refs)

    return response

  @monorail_servicer.PRPCMethod
  def UpdateApproval(self, mc, request):
    """Update an approval and return the updated approval in a reponse proto."""
    project, issue, config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, use_cache=False)

    approval_fd = tracker_bizobj.FindFieldDef(
        request.field_ref.field_name, config)
    if not approval_fd:
      raise exceptions.NoSuchFieldDefException()
    if request.HasField('approval_delta'):
      approval_delta = converters.IngestApprovalDelta(
          mc.cnxn, self.services.user, request.approval_delta,
          mc.auth.user_id, config)
    else:
      approval_delta = tracker_pb2.ApprovalDelta()
    attachments = converters.IngestAttachmentUploads(request.uploads)

    with work_env.WorkEnv(mc, self.services) as we:
      av, _comment = we.UpdateIssueApproval(
          issue.issue_id, approval_fd.field_id, approval_delta,
          request.comment_content, request.is_description,
          attachments=attachments, send_email=request.send_email,
          kept_attachments=list(request.kept_attachments))

    with mc.profiler.Phase('converting to response objects'):
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, av.approver_ids, [av.setter_id])
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)
      response = issues_pb2.UpdateApprovalResponse()
      response.approval.CopyFrom(converters.ConvertApproval(
          av, users_by_id, config))

    return response

  @monorail_servicer.PRPCMethod
  def ConvertIssueApprovalsTemplate(self, mc, request):
    """Update an issue's existing approvals structure to match the one of the
       given template."""

    if not request.issue_ref.local_id or not request.issue_ref.project_name:
      raise exceptions.InputException('Param `issue_ref.local_id` empty')
    if not request.template_name:
      raise exceptions.InputException('Param `template_name` empty')

    project, issue, config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      we.ConvertIssueApprovalsTemplate(
          config, issue, request.template_name, request.comment_content,
          send_email=request.send_email)
      related_refs = we.GetRelatedIssueRefs([issue])

    with mc.profiler.Phase('making user views'):
      users_involved_in_issue = tracker_bizobj.UsersInvolvedInIssues([issue])
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved_in_issue)
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)

    with mc.profiler.Phase('converting to response objects'):
      response = issues_pb2.ConvertIssueApprovalsTemplateResponse()
      response.issue.CopyFrom(converters.ConvertIssue(
          issue, users_by_id, related_refs, config))
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
      # TODO(jrobbins): support linked accounts me_user_ids.
      canned_query, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
          [mc.auth.user_id], canned_query)
    else:
      canned_query = None

    if request.query:
      query, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
          [mc.auth.user_id], request.query)
    else:
      query = None

    with work_env.WorkEnv(mc, self.services) as we:
      project = we.GetProjectByName(request.project_name)
      results, unsupported_fields, limit_reached = we.SnapshotCountsQuery(
          project, request.timestamp, request.group_by,
          label_prefix=request.label_prefix,
          query=query, canned_query=canned_query)
    if request.group_by == 'owner':
      # Map user ids to emails.
      snapshot_counts = [
        issues_pb2.IssueSnapshotCount(
          dimension=self.services.user.GetUser(mc.cnxn, key).email,
          count=result) for key, result in results.iteritems()
      ]
    else:
      snapshot_counts = [
        issues_pb2.IssueSnapshotCount(dimension=key, count=result)
          for key, result in results.items()
      ]
    response = issues_pb2.IssueSnapshotResponse()
    response.snapshot_count.extend(snapshot_counts)
    response.unsupported_field.extend(unsupported_fields)
    response.unsupported_field.extend(warnings)
    response.search_limit_reached = limit_reached
    return response

  @monorail_servicer.PRPCMethod
  def PresubmitIssue(self, mc, request):
    """Provide the UI with warnings and suggestions."""
    project, issue, config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, issue_required=False)

    with mc.profiler.Phase('making user views'):
      try:
        proposed_owner_id = converters.IngestUserRef(
            mc.cnxn, request.issue_delta.owner_ref, self.services.user)
      except exceptions.NoSuchUserException:
        proposed_owner_id = 0

      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, [proposed_owner_id])
      proposed_owner_view = users_by_id[proposed_owner_id]

    with mc.profiler.Phase('Applying IssueDelta'):
      if issue:
        proposed_issue = copy.deepcopy(issue)
      else:
        proposed_issue = tracker_pb2.Issue(
          owner_id=framework_constants.NO_USER_SPECIFIED,
          project_id=config.project_id)
      issue_delta = converters.IngestIssueDelta(
          mc.cnxn, self.services, request.issue_delta, config, None,
          ignore_missing_objects=True)
      tracker_bizobj.ApplyIssueDelta(
          mc.cnxn, self.services.issue, proposed_issue, issue_delta, config)

    with mc.profiler.Phase('applying rules'):
      _, traces = filterrules_helpers.ApplyFilterRules(
          mc.cnxn, self.services, proposed_issue, config)
      logging.info('proposed_issue is now: %r', proposed_issue)
      logging.info('traces are: %r', traces)

    with mc.profiler.Phase('making derived user views'):
      derived_users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, [proposed_issue.derived_owner_id],
          proposed_issue.derived_cc_ids)
      framework_views.RevealAllEmailsToMembers(
          mc.auth, project, derived_users_by_id)

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

  @monorail_servicer.PRPCMethod
  def RerankBlockedOnIssues(self, mc, request):
    """Rerank the blocked on issues for the given issue ref."""
    moved_issue_id, target_issue_id = converters.IngestIssueRefs(
        mc.cnxn, [request.moved_ref, request.target_ref], self.services)
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      we.RerankBlockedOnIssues(
          issue, moved_issue_id, target_issue_id, request.split_above)

    with work_env.WorkEnv(mc, self.services) as we:
      issue = we.GetIssue(issue.issue_id)
      related_refs = we.GetRelatedIssueRefs([issue])

    with mc.profiler.Phase('converting to response objects'):
      converted_issue_refs = converters.ConvertIssueRefs(
          issue.blocked_on_iids, related_refs)
      result = issues_pb2.RerankBlockedOnIssuesResponse(
          blocked_on_issue_refs=converted_issue_refs)

    return result

  @monorail_servicer.PRPCMethod
  def DeleteIssue(self, mc, request):
    """Mark or unmark the given issue as deleted."""
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, view_deleted=True)

    with work_env.WorkEnv(mc, self.services) as we:
      we.DeleteIssue(issue, request.delete)

    result = issues_pb2.DeleteIssueResponse()
    return result

  @monorail_servicer.PRPCMethod
  def DeleteIssueComment(self, mc, request):
    """Mark or unmark the given comment as deleted."""
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      comments = we.ListIssueComments(issue)
      if request.sequence_num >= len(comments):
        raise exceptions.InputException('Invalid sequence number.')
      we.DeleteComment(issue, comments[request.sequence_num], request.delete)

    result = issues_pb2.DeleteIssueCommentResponse()
    return result

  @monorail_servicer.PRPCMethod
  def DeleteAttachment(self, mc, request):
    """Mark or unmark the given attachment as deleted."""
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      comments = we.ListIssueComments(issue)
      if request.sequence_num >= len(comments):
        raise exceptions.InputException('Invalid sequence number.')
      we.DeleteAttachment(
          issue, comments[request.sequence_num], request.attachment_id,
          request.delete)

    result = issues_pb2.DeleteAttachmentResponse()
    return result

  @monorail_servicer.PRPCMethod
  def FlagIssues(self, mc, request):
    """Flag or unflag the given issues as spam."""
    if not request.issue_refs:
      raise exceptions.InputException('Param `issue_refs` empty.')

    _project, issue_ids, _config = self._GetProjectIssueIDsAndConfig(
        mc, request.issue_refs)
    with work_env.WorkEnv(mc, self.services) as we:
      issues_by_id = we.GetIssuesDict(issue_ids, use_cache=False)
      we.FlagIssues(list(issues_by_id.values()), request.flag)

    result = issues_pb2.FlagIssuesResponse()
    return result

  @monorail_servicer.PRPCMethod
  def FlagComment(self, mc, request):
    """Flag or unflag the given comment as spam."""
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      comments = we.ListIssueComments(issue)
      if request.sequence_num >= len(comments):
        raise exceptions.InputException('Invalid sequence number.')
      we.FlagComment(issue, comments[request.sequence_num], request.flag)

    result = issues_pb2.FlagCommentResponse()
    return result

  @monorail_servicer.PRPCMethod
  def ListIssuePermissions(self, mc, request):
    """List the permissions for the current user in the given issue."""
    project, issue, config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, use_cache=False, view_deleted=True)

    perms = permissions.UpdateIssuePermissions(
        mc.perms, project, issue, mc.auth.effective_ids, config=config)

    return issues_pb2.ListIssuePermissionsResponse(
        permissions=sorted(perms.perm_names))

  @monorail_servicer.PRPCMethod
  def MoveIssue(self, mc, request):
    """Move an issue to another project."""
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      target_project = we.GetProjectByName(request.target_project_name)
      moved_issue = we.MoveIssue(issue, target_project)

    result = issues_pb2.MoveIssueResponse(
        new_issue_ref=converters.ConvertIssueRef(
            (moved_issue.project_name, moved_issue.local_id)))
    return result

  @monorail_servicer.PRPCMethod
  def CopyIssue(self, mc, request):
    """Copy an issue."""
    _project, issue, _config = self._GetProjectIssueAndConfig(
        mc, request.issue_ref, use_cache=False)

    with work_env.WorkEnv(mc, self.services) as we:
      target_project = we.GetProjectByName(request.target_project_name)
      copied_issue = we.CopyIssue(issue, target_project)

    result = issues_pb2.CopyIssueResponse(
        new_issue_ref=converters.ConvertIssueRef(
            (copied_issue.project_name, copied_issue.local_id)))
    return result
