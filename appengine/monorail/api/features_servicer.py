# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import logging

from api import monorail_servicer
from api import converters
from api.api_proto import common_pb2
from api.api_proto import features_pb2
from api.api_proto import features_prpc_pb2
from businesslogic import work_env
from features import features_bizobj
from framework import exceptions
from framework import framework_bizobj
from framework import framework_views
from framework import paginate
from services import features_svc
from tracker import tracker_bizobj


class FeaturesServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Features objects.

  Each API request is implemented with a method as defined in the .proto
  file that does any request-specific validation, uses work_env to
  safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = features_prpc_pb2.FeaturesServiceDescription

  @monorail_servicer.PRPCMethod
  def ListHotlistsByUser(self, mc, request):
    """Return the specified project config."""
    user_id = converters.IngestUserRefs(
        mc.cnxn, [request.user], self.services.user)[0]

    with work_env.WorkEnv(mc, self.services) as we:
      # List hotlists for the currently authenticated user.
      hotlists = we.ListHotlistsByUser(user_id)

    with mc.profiler.Phase('making user views'):
      users_involved = features_bizobj.UsersOwnersOfHotlists(hotlists)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, None, users_by_id)

    converted_hotlists = [
        converters.ConvertHotlist(hotlist, users_by_id)
        for hotlist in hotlists]

    result = features_pb2.ListHotlistsByUserResponse(
        hotlists=converted_hotlists)

    return result

  @monorail_servicer.PRPCMethod
  def GetHotlistStarCount(self, mc, request):
    """Get the star count for the specified hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      star_count = we.GetHotlistStarCount(hotlist_id)

    result = features_pb2.GetHotlistStarCountResponse(star_count=star_count)
    return result

  @monorail_servicer.PRPCMethod
  def StarHotlist(self, mc, request):
    """Star the specified hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      we.StarHotlist(hotlist_id, request.starred)
      star_count = we.GetHotlistStarCount(hotlist_id)

    result = features_pb2.StarHotlistResponse(star_count=star_count)
    return result

  @monorail_servicer.PRPCMethod
  def ListHotlistIssues(self, mc, request):
    """Get the issues on the specified hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      hotlist_items = we.GetHotlist(hotlist_id).items
      issue_ids = [item.issue_id for item in hotlist_items]
      issues = we.GetIssuesDict(issue_ids)

      projects = we.GetProjectsByName([
          issue.project_name for issue in issues.itervalues()])
      configs = we.GetProjectConfigs([
          project.project_id for project in projects.itervalues()])
      configs = {
          project.project_name: configs[project.project_id]
          for project in projects.itervalues()}
      related_refs = we.GetRelatedIssueRefs(issues.itervalues())

    with mc.profiler.Phase('making user views'):
      users_involved = set(item.adder_id for item in hotlist_items)
      users_involved.update(
          tracker_bizobj.UsersInvolvedInIssues(issues.itervalues()))
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, None, users_by_id)

    hotlist_items = [
        hotlist_item for hotlist_item in hotlist_items
        if hotlist_item.issue_id in issues]

    start, max_items = converters.IngestPagination(request.pagination)
    pagination = paginate.ArtifactPagination(
        hotlist_items, max_items, start, None, None)

    result = features_pb2.ListHotlistIssuesResponse(
        items=[
            converters.ConvertHotlistItem(
                hotlist_item, issues,  users_by_id, related_refs, configs)
            for hotlist_item in pagination.visible_results])
    return result

  @monorail_servicer.PRPCMethod
  def DismissCue(self, mc, request):
    """Don't show the given cue to the logged in user anymore."""
    cue_id = request.cue_id

    with work_env.WorkEnv(mc, self.services) as we:
      we.DismissCue(cue_id)

    result = features_pb2.DismissCueResponse()
    return result

  @monorail_servicer.PRPCMethod
  def CreateHotlist(self, mc, request):
    """Create a new hotlist."""
    editor_ids = converters.IngestUserRefs(
        mc.cnxn, request.editor_refs, self.services.user)
    issue_ids = converters.IngestIssueRefs(
        mc.cnxn, request.issue_refs, self.services)

    with work_env.WorkEnv(mc, self.services) as we:
      we.CreateHotlist(
          request.name, request.summary, request.description, editor_ids,
          issue_ids, request.is_private)

    result = features_pb2.CreateHotlistResponse()
    return result

  @monorail_servicer.PRPCMethod
  def CheckHotlistName(self, mc, request):
    """Check that a hotlist name is valid and not already in use."""
    with work_env.WorkEnv(mc, self.services) as we:
      we.CheckHotlistName(request.name)
    return features_pb2.CheckHotlistNameResponse()

  @monorail_servicer.PRPCMethod
  def RemoveIssuesFromHotlists(self, mc, request):
    """Remove the given issues from the given hotlists."""
    hotlist_ids = converters.IngestHotlistRefs(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_refs)
    issue_ids = converters.IngestIssueRefs(
        mc.cnxn, request.issue_refs, self.services)

    with work_env.WorkEnv(mc, self.services) as we:
      we.RemoveIssuesFromHotlists(hotlist_ids, issue_ids)

    result = features_pb2.RemoveIssuesFromHotlistsResponse()
    return result
