# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from api import converters
from api import monorail_servicer
from api import converters
from api.api_proto import users_pb2
from api.api_proto import users_prpc_pb2
from api.api_proto import user_objects_pb2
from businesslogic import work_env
from framework import authdata
from framework import framework_views
from framework import permissions

class UsersServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to User objects.

  Each API request is implemented with a method as defined in the
  .proto file that does any request-specific validation, uses work_env
  to safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = users_prpc_pb2.UsersServiceDescription

  @monorail_servicer.PRPCMethod
  def GetUser(self, mc, request):
    """Return info about the specified user."""
    with work_env.WorkEnv(mc, self.services) as we:
      users, linked_user_ids = we.ListReferencedUsers(
          [request.user_ref.display_name])
      linked_user_views = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, linked_user_ids)

    with mc.profiler.Phase('converting to response objects'):
      response_users = converters.ConvertUsers(users, linked_user_views)

    return response_users[0]

  @monorail_servicer.PRPCMethod
  def ListReferencedUsers(self, mc, request):
    """Return the list of existing users in a response proto."""
    emails = request.emails
    if request.user_refs:
      emails = [user_ref.display_name for user_ref in request.user_refs]
    with work_env.WorkEnv(mc, self.services) as we:
      users, linked_user_ids = we.ListReferencedUsers(emails)
      linked_user_views = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, linked_user_ids)

    with mc.profiler.Phase('converting to response objects'):
      response_users = converters.ConvertUsers(users, linked_user_views)
      response = users_pb2.ListReferencedUsersResponse(users=response_users)

    return response

  @monorail_servicer.PRPCMethod
  def GetMemberships(self, mc, request):
    """Return the user groups for the given user visible to the requester."""
    user_id = converters.IngestUserRef(
        mc.cnxn, request.user_ref, self.services.user)

    with work_env.WorkEnv(mc, self.services) as we:
      group_ids = we.GetMemberships(user_id)

    with mc.profiler.Phase('converting to response objects'):
      groups_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, group_ids)
      group_refs = converters.ConvertUserRefs(
          group_ids, [], groups_by_id, True)

      return users_pb2.GetMembershipsResponse(group_refs=group_refs)

  @monorail_servicer.PRPCMethod
  def GetUserStarCount(self, mc, request):
    """Return the star count for a given user."""
    user_id = converters.IngestUserRef(
        mc.cnxn, request.user_ref, self.services.user)

    with work_env.WorkEnv(mc, self.services) as we:
      star_count = we.GetUserStarCount(user_id)

    result = users_pb2.GetUserStarCountResponse(star_count=star_count)
    return result

  @monorail_servicer.PRPCMethod
  def StarUser(self, mc, request):
    """Star a given user."""
    user_id = converters.IngestUserRef(
        mc.cnxn, request.user_ref, self.services.user)

    with work_env.WorkEnv(mc, self.services) as we:
      we.StarUser(user_id, request.starred)
      star_count = we.GetUserStarCount(user_id)

    result = users_pb2.StarUserResponse(star_count=star_count)
    return result

  @monorail_servicer.PRPCMethod
  def SetExpandPermsPreference(self, mc, request):
    """Set a users preference on whether to expand perms by default."""
    with work_env.WorkEnv(mc, self.services) as we:
      we.UpdateUserSettings(
          mc.auth.user_pb, keep_people_perms_open=request.expand_perms)

    result = users_pb2.SetExpandPermsPreferenceResponse()
    return result

  def _SignedInOrSpecifiedUser(self, mc, request):
    """If request specifies a user, return it.  Otherwise signed-in user."""
    user_id = mc.auth.user_id
    if request.HasField('user_ref'):
      user_id = converters.IngestUserRef(
          mc.cnxn, request.user_ref, self.services.user)
    return user_id

  @monorail_servicer.PRPCMethod
  def GetSavedQueries(self, mc, request):
    """Get a user's saved queries."""
    user_id = self._SignedInOrSpecifiedUser(mc, request)

    # Only site admins can view other user's saved queries.
    if user_id != mc.auth.user_id and not mc.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
        'You are not allowed to view this user\'s saved queries')

    saved_queries = self.services.features.GetSavedQueriesByUserID(
        mc.cnxn, user_id)
    return users_pb2.GetSavedQueriesResponse(
        saved_queries=converters.IngestSavedQueries(mc.cnxn,
            self.services.project, saved_queries))

  @monorail_servicer.PRPCMethod
  def GetUserPrefs(self, mc, request):
    """Get a user's preferences."""
    with work_env.WorkEnv(mc, self.services) as we:
      userprefs = we.GetUserPrefs(self._SignedInOrSpecifiedUser(mc, request))

    result = users_pb2.GetUserPrefsResponse(
        prefs=converters.ConvertPrefValues(userprefs.prefs))
    return result

  @monorail_servicer.PRPCMethod
  def SetUserPrefs(self, mc, request):
    """Add to or set a users preferences."""
    with work_env.WorkEnv(mc, self.services) as we:
      pref_values = converters.IngestPrefValues(request.prefs)
      we.SetUserPrefs(self._SignedInOrSpecifiedUser(mc, request), pref_values)

    result = users_pb2.SetUserPrefsResponse()
    return result

  @monorail_servicer.PRPCMethod
  def InviteLinkedParent(self, mc, request):
    """Create a linked account invite."""
    with work_env.WorkEnv(mc, self.services) as we:
      we.InviteLinkedParent(request.email)

    result = users_pb2.InviteLinkedParentResponse()
    return result

  @monorail_servicer.PRPCMethod
  def AcceptLinkedChild(self, mc, request):
    """Link a child account that has invited this account as parent."""
    child_id = self.services.user.LookupUserID(mc.cnxn, request.email)
    with work_env.WorkEnv(mc, self.services) as we:
      we.AcceptLinkedChild(child_id)

    result = users_pb2.AcceptLinkedChildResponse()
    return result

  @monorail_servicer.PRPCMethod
  def UnlinkAccounts(self, mc, request):
    """Unlink a specificed parent and child account."""
    parent_id, child_id = converters.IngestUserRefs(
        mc.cnxn, [request.parent, request.child], self.services.user)
    with work_env.WorkEnv(mc, self.services) as we:
      we.UnlinkAccounts(parent_id, child_id)

    result = users_pb2.UnlinkAccountsResponse()
    return result

  @monorail_servicer.PRPCMethod
  def GetUsersProjects(self, mc, request):
    user_ids = converters.IngestUserRefs(
        mc.cnxn, request.user_refs, self.services.user)
    user_auths = [
        authdata.AuthData.FromUserID(mc.cnxn, user_id, self.services)
        for user_id in user_ids]

    result = users_pb2.GetUsersProjectsResponse()
    with work_env.WorkEnv(mc, self.services) as we:
      for user_ref, auth in zip(request.user_refs, user_auths):
        starred = we.ListStarredProjects(auth.user_id)
        owner, _archived, member, contrib = we.GetUserProjects(
            auth.effective_ids)
        user_projects = result.users_projects.add()
        user_projects.user_ref.CopyFrom(user_ref)
        user_projects.owner_of.extend(p.project_name for p in owner)
        user_projects.member_of.extend(p.project_name for p in member)
        user_projects.contributor_to.extend(p.project_name for p in contrib)
        user_projects.starred_projects.extend(p.project_name for p in starred)

    return result
