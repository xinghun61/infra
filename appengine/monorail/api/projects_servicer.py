# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import logging

from api import monorail_servicer
from api import converters
from api.api_proto import projects_pb2
from api.api_proto import project_objects_pb2
from api.api_proto import projects_prpc_pb2
from businesslogic import work_env
from framework import framework_views
from framework import permissions
from project import project_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers


class ProjectsServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Project objects.

  Each API request is implemented with a method as defined in the .proto
  file that does any request-specific validation, uses work_env to
  safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = projects_prpc_pb2.ProjectsServiceDescription

  def _GetProject(self, mc, request, use_cache=True):
    """Get the project object specified in the request."""
    with work_env.WorkEnv(mc, self.services, phase='getting project') as we:
      project = we.GetProjectByName(request.project_name, use_cache=use_cache)
      # Perms in this project are already looked up in MonorailServicer.
    return project

  @monorail_servicer.PRPCMethod
  def ListProjects(self, _mc, _request):
    return projects_pb2.ListProjectsResponse(
        projects=[
            project_objects_pb2.Project(name='One'),
            project_objects_pb2.Project(name='Two')],
        next_page_token='next...')

  @monorail_servicer.PRPCMethod
  def GetConfig(self, mc, request):
    """Return the specified project config."""
    project = self._GetProject(mc, request)

    with work_env.WorkEnv(mc, self.services) as we:
      config = we.GetProjectConfig(project.project_id)

    with mc.profiler.Phase('making user views'):
      users_involved = tracker_bizobj.UsersInvolvedInConfig(config)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)

      label_ids = tracker_bizobj.LabelIDsInvolvedInConfig(config)
      labels_by_id = {
        label_id: self.services.config.LookupLabel(
            mc.cnxn, config.project_id, label_id)
        for label_id in label_ids}

    result = converters.ConvertConfig(
        project, config, users_by_id, labels_by_id)
    return result

  @monorail_servicer.PRPCMethod
  def GetCustomPermissions(self, mc, request):
    """Return the custom permissions for the given project."""
    project = self._GetProject(mc, request)
    custom_permissions = permissions.GetCustomPermissions(project)

    result = projects_pb2.GetCustomPermissionsResponse(
        permissions=custom_permissions)
    return result

  @monorail_servicer.PRPCMethod
  def GetVisibleMembers(self, mc, request):
    """Return the members of the project that the user can see."""
    project = self._GetProject(mc, request)

    users_by_id = tracker_helpers.GetVisibleMembers(mc, project, self.services)

    user_refs = converters.ConvertUserRefs(
        sorted(users_by_id), [], users_by_id, True)
    group_refs = converters.ConvertUserRefs(
        sorted(uv.user_id for uv in users_by_id.values() if uv.is_group), [],
        users_by_id, True)

    result = projects_pb2.GetVisibleMembersResponse(
        user_refs=user_refs, group_refs=group_refs)
    return result

  @monorail_servicer.PRPCMethod
  def GetLabelOptions(self, mc, request):
    """Return the label options for autocomplete for the given project."""
    project = self._GetProject(mc, request)

    with work_env.WorkEnv(mc, self.services) as we:
      config = we.GetProjectConfig(project.project_id)

    label_options = tracker_helpers.GetLabelOptions(
        config, permissions.GetCustomPermissions(project))
    label_defs = [
        project_objects_pb2.LabelDef(
            label=label['name'],
            docstring=label['doc'])
        for label in label_options]

    result = projects_pb2.GetLabelOptionsResponse(
        label_options=label_defs,
        exclusive_label_prefixes=config.exclusive_label_prefixes)
    return result

  @monorail_servicer.PRPCMethod
  def ListStatuses(self, mc, request):
    """Return all well-known statuses in the specified project."""
    project = self._GetProject(mc, request)

    with work_env.WorkEnv(mc, self.services) as we:
      config = we.GetProjectConfig(project.project_id)

    status_defs = [
        converters.ConvertStatusDef(sd)
        for sd in config.well_known_statuses]
    statuses_offer_merge = [
        converters.ConvertStatusRef(sd.status, None, config)
        for sd in config.well_known_statuses
        if sd.status in config.statuses_offer_merge]

    result = projects_pb2.ListStatusesResponse(
        status_defs=status_defs,
        statuses_offer_merge=statuses_offer_merge,
        restrict_to_known=config.restrict_to_known)
    return result

  @monorail_servicer.PRPCMethod
  def ListComponents(self, mc, request):
    """Return all component defs in the specified project."""
    project = self._GetProject(mc, request)

    with work_env.WorkEnv(mc, self.services) as we:
      config = we.GetProjectConfig(project.project_id)

    with mc.profiler.Phase('making user views'):
      users_by_id = {}
      if request.include_admin_info:
        users_involved = tracker_bizobj.UsersInvolvedInConfig(config)
        users_by_id = framework_views.MakeAllUserViews(
            mc.cnxn, self.services.user, users_involved)
        framework_views.RevealAllEmailsToMembers(mc.auth, project, users_by_id)

    with mc.profiler.Phase('looking up labels'):
      labels_by_id = {}
      if request.include_admin_info:
        label_ids = tracker_bizobj.LabelIDsInvolvedInConfig(config)
        labels_by_id = {
          label_id: self.services.config.LookupLabel(
              mc.cnxn, config.project_id, label_id)
          for label_id in label_ids}

    component_defs = [
        converters.ConvertComponentDef(
            cd, users_by_id, labels_by_id, request.include_admin_info)
        for cd in config.component_defs]

    result = projects_pb2.ListComponentsResponse(
        component_defs=component_defs)
    return result

  @monorail_servicer.PRPCMethod
  def ListFields(self, mc, request):
    """List all fields for the specified project."""
    project = self._GetProject(mc, request)

    with work_env.WorkEnv(mc, self.services) as we:
      config = we.GetProjectConfig(project.project_id)

    users_by_id = {}
    users_for_perm = {}
    # Only look for members if user choices are requested and there are user
    # fields that need permissions.
    if request.include_user_choices:
      perms_needed = {
          fd.needs_perm
          for fd in config.field_defs
          if fd.needs_perm and not fd.is_deleted}
      if perms_needed:
        users_by_id = tracker_helpers.GetVisibleMembers(
            mc, project, self.services)
        effective_ids_by_user = self.services.usergroup.LookupAllMemberships(
            mc.cnxn, users_by_id)
        users_for_perm = project_helpers.UsersWithPermsInProject(
            project, perms_needed, users_by_id, effective_ids_by_user)

    field_defs = [
        converters.ConvertFieldDef(
            fd, users_for_perm.get(fd.needs_perm, []), users_by_id, config,
            request.include_admin_info)
        for fd in config.field_defs
        if not fd.is_deleted]

    result = projects_pb2.ListFieldsResponse(field_defs=field_defs)
    return result

  @monorail_servicer.PRPCMethod
  def GetProjectStarCount(self, mc, request):
    """Get the star count for the specified project."""
    project = self._GetProject(mc, request)

    with work_env.WorkEnv(mc, self.services) as we:
      star_count = we.GetProjectStarCount(project.project_id)

    result = projects_pb2.GetProjectStarCountResponse(star_count=star_count)
    return result

  @monorail_servicer.PRPCMethod
  def StarProject(self, mc, request):
    """Star the specified project."""
    project = self._GetProject(mc, request)

    with work_env.WorkEnv(mc, self.services) as we:
      we.StarProject(project.project_id, request.starred)
      star_count = we.GetProjectStarCount(project.project_id)

    result = projects_pb2.StarProjectResponse(star_count=star_count)
    return result

  @monorail_servicer.PRPCMethod
  def GetUserProjects(self, mc, _request):
    """Get the projects the user is involved in."""
    with work_env.WorkEnv(mc, self.services) as we:
      starred = we.ListStarredProjects()
      owner, _archived, member, contrib = we.GetUserProjects(
          mc.auth.effective_ids)

    result = projects_pb2.GetUserProjectsResponse(
        owner_of=[p.project_name for p in owner],
        member_of=[p.project_name for p in member],
        contributor_to=[p.project_name for p in contrib],
        starred_projects=[p.project_name for p in starred])
    return result

  @monorail_servicer.PRPCMethod
  def CheckProjectName(self, mc, request):
    """Check that a project name is valid and not already in use."""
    with work_env.WorkEnv(mc, self.services) as we:
      error = we.CheckProjectName(request.project_name)
    result = projects_pb2.CheckProjectNameResponse(error=error)
    return result
