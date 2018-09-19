# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""WorkEnv is a context manager and API for high-level operations.

A work environment is used by request handlers for the legacy UI, v1
API, and v2 API.  The WorkEnvironment operations are a common code
path that does permission checking, rate limiting, and other systemic
functionality so that that code is not duplicated in multiple request
handlers.

Responsibilities of request handers (legacy UI and external API) and associated
frameworks:
+ API: check oauth client whitelist or XSRF token
+ Rate-limiting
+ Create a MonorailContext (or MonorailRequest) object:
  - Parse the request, including syntactic validation, e.g, non-negative ints
  - Authenticate the requesting user
+ Call the WorkEnvironment to perform the requested action
  - Catch exceptions and generate error messages
+ UI: Decide screen flow, and on-page online-help
+ Render the result business objects as UI HTML or API response protobufs.

Responsibilities of WorkEnv:
+ Most monitoring, profiling, and logging
+ Apply business rules:
  - Check permissions
  - Detailed validation of request parameters
  - Raise exceptions to indicate problems
+ Call the services layer to make DB changes
+ Enqueue tasks for background follow-up work:
  - E.g., email notifications

Responsibilities of the Services layer:
+ CRUD operations on objects in the database
+ App-specific interface around external services:
  - E.g., GAE search, GCS, monorail-predict
"""

import logging
import time

from features import features_constants
from features import send_notifications
from features import features_bizobj
from features import hotlist_helpers
from framework import framework_bizobj
from framework import exceptions
from framework import framework_helpers
from framework import permissions
from search import frontendsearchpipeline
from services import project_svc
from sitewide import sitewide_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from proto import project_pb2


# TODO(jrobbins): break this file into one facade plus ~5
# implementation parts that roughly correspond to services files.


class WorkEnv(object):

  def __init__(self, mc, services, phase=None):
    self.mc = mc
    self.services = services
    self.phase = phase

  def __enter__(self):
    if self.mc.profiler and self.phase:
      self.mc.profiler.StartPhase(name=self.phase)
    return self  # The instance of this class is the context object.

  def __exit__(self, exception_type, value, traceback):
    if self.mc.profiler and self.phase:
      self.mc.profiler.EndPhase()
    return False  # Re-raise any exception in the with-block.

  def _UserCanViewProject(self, project):
    """Test if the user may view the given project."""
    return permissions.UserCanViewProject(
        self.mc.auth.user_pb, self.mc.auth.effective_ids, project)

  def _FilterVisibleProjectsDict(self, projects):
    """Filter out projects the user doesn't have permission to view."""
    return {
        key: proj
        for key, proj in projects.iteritems()
        if self._UserCanViewProject(proj)}

  def _AssertPermInProject(self, perm, project):
    """Make sure the user may use perm in the given project."""
    permitted = self.mc.perms.CanUsePerm(
        perm, self.mc.auth.effective_ids, project, [])
    if not permitted:
      raise permissions.PermissionException(
        'User lacks permission %r in project %s' % (perm, project.project_name))

  def _UserCanViewIssue(self, issue, allow_viewing_deleted=False):
    """Test if the user may view the issue."""
    project = self.GetProject(issue.project_id)
    config = self.GetProjectConfig(issue.project_id)
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, self.mc.auth.effective_ids, config)
    permit_view = permissions.CanViewIssue(
        self.mc.auth.effective_ids, self.mc.perms, project, issue,
        allow_viewing_deleted=allow_viewing_deleted,
        granted_perms=granted_perms)
    return project, granted_perms, permit_view

  def _AssertUserCanViewIssue(self, issue, allow_viewing_deleted=False):
    """Make sure the user may view the issue."""
    project, granted_perms, permit_view = self._UserCanViewIssue(
        issue, allow_viewing_deleted)
    if not permit_view:
      raise permissions.PermissionException(
          'User is not allowed to view this issue')
    return project, granted_perms

  def _AssertPermInIssue(self, issue, perm):
    """Make sure the user may use perm on the given issue."""
    project, granted_perms = self._AssertUserCanViewIssue(
        issue, allow_viewing_deleted=True)
    permitted = self.mc.perms.CanUsePerm(
        perm, self.mc.auth.effective_ids, project,
        permissions.GetRestrictions(issue), granted_perms=granted_perms)
    if not permitted:
      raise permissions.PermissionException(
        'User lacks permission %r in issue' % perm)

  def _AssertUserCanViewHotlist(self, hotlist):
    """Make sure the user may view the hotlist."""
    if not permissions.CanViewHotlist(self.mc.auth.effective_ids, hotlist):
      raise permissions.PermissionException(
          'User is not allowed to view this hotlist')

  def _AssertUserCanEditHotlist(self, hotlist):
    if not permissions.CanEditHotlist(self.mc.auth.effective_ids, hotlist):
      raise permissions.PermissionException(
          'User is not allowed to edit this hotlist')

  ### Site methods

  # FUTURE: GetSiteReadOnlyState()
  # FUTURE: SetSiteReadOnlyState()
  # FUTURE: GetSiteBannerMessage()
  # FUTURE: SetSiteBannerMessage()

  ### Project methods

  def CreateProject(
      self, project_name, owner_ids, committer_ids, contributor_ids,
      summary, description, state=project_pb2.ProjectState.LIVE,
      access=None, read_only_reason=None, home_page=None, docs_url=None,
      source_url=None, logo_gcs_id=None, logo_file_name=None):
    """Create and store a Project with the given attributes.

    Args:
      cnxn: connection to SQL database.
      project_name: a valid project name, all lower case.
      owner_ids: a list of user IDs for the project owners.
      committer_ids: a list of user IDs for the project members.
      contributor_ids: a list of user IDs for the project contributors.
      summary: one-line explanation of the project.
      description: one-page explanation of the project.
      state: a project state enum defined in project_pb2.
      access: optional project access enum defined in project.proto.
      read_only_reason: if given, provides a status message and marks
        the project as read-only.
      home_page: home page of the project
      docs_url: url to redirect to for wiki/documentation links
      source_url: url to redirect to for source browser links
      logo_gcs_id: google storage object id of the project's logo
      logo_file_name: uploaded file name of the project's logo

    Returns:
      The int project_id of the new project.

    Raises:
      ProjectAlreadyExists: A project with that name already exists.
    """
    if not permissions.CanCreateProject(self.mc.perms):
      raise permissions.PermissionException(
          'User is not allowed to create a project')

    with self.mc.profiler.Phase('creating project %r' % project_name):
      project_id = self.services.project.CreateProject(
          self.mc.cnxn, project_name, owner_ids, committer_ids, contributor_ids,
          summary, description, state=state, access=access,
          read_only_reason=read_only_reason, home_page=home_page,
          docs_url=docs_url, source_url=source_url, logo_gcs_id=logo_gcs_id,
          logo_file_name=logo_file_name)
      self.services.template.CreateDefaultProjectTemplates(self.mc.cnxn,
          project_id)
    return project_id

  def ListProjects(self, use_cache=True):
    """Return a list of project IDs that the current user may view."""
    # Note: No permission checks because anyone can list projects, but
    # the results are filtered by permission to view each project.

    with self.mc.profiler.Phase('list projects for %r' % self.mc.auth.user_id):
      project_ids = self.services.project.GetVisibleLiveProjects(
          self.mc.cnxn, self.mc.auth.user_pb, self.mc.auth.effective_ids,
          use_cache=use_cache)

    project_ids = sorted(project_ids)
    return project_ids

  def CheckProjectName(self, project_name):
    """Check that a project name is valid and not already in use.

    Args:
      project_name: str the project name to check.

    Returns:
      None if the user can create a project with that name, or a string with the
      reason the name can't be used.

    Raises:
      PermissionException: The user is not allowed to create a project.
    """
    # We check that the user can create a project so we don't leak information
    # about project names.
    if not permissions.CanCreateProject(self.mc.perms):
      raise permissions.PermissionException(
          'User is not allowed to create a project')

    with self.mc.profiler.Phase('checking project name %s' % project_name):
      if self.services.project.LookupProjectIDs(self.mc.cnxn, [project_name]):
        return 'That project name is not available.'
    return None

  def GetProjects(self, project_ids, use_cache=True):
    """Return the specified projects.

    Args:
      project_ids: int project_ids of the projects to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified projects.

    Raises:
      NoSuchProjectException: There is no project with that ID.
    """
    with self.mc.profiler.Phase('getting projects %r' % project_ids):
      projects = self.services.project.GetProjects(
          self.mc.cnxn, project_ids, use_cache=use_cache)

    projects = self._FilterVisibleProjectsDict(projects)
    return projects

  def GetProject(self, project_id, use_cache=True):
    """Return the specified project.

    Args:
      project_id: int project_id of the project to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified project.

    Raises:
      NoSuchProjectException: There is no project with that ID.
    """
    projects = self.GetProjects([project_id], use_cache=use_cache)
    if project_id not in projects:
      raise permissions.PermissionException(
          'User is not allowed to view this project')
    return projects[project_id]

  def GetProjectsByName(self, project_names, use_cache=True):
    """Return the named project.

    Args:
      project_names: string names of the projects to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified projects.
    """
    with self.mc.profiler.Phase('getting projects %r' % project_names):
      projects = self.services.project.GetProjectsByName(
          self.mc.cnxn, project_names, use_cache=use_cache)

    for pn in project_names:
      if pn not in projects:
        raise exceptions.NoSuchProjectException('Project %r not found.' % pn)

    projects = self._FilterVisibleProjectsDict(projects)
    return projects

  def GetProjectByName(self, project_name, use_cache=True):
    """Return the named project.

    Args:
      project_name: string name of the project to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified project.

    Raises:
      NoSuchProjectException: There is no project with that name.
    """
    projects = self.GetProjectsByName([project_name], use_cache)
    if not projects:
      raise permissions.PermissionException(
          'User is not allowed to view this project')

    return projects[project_name]

  def GetUserRolesInAllProjects(self, viewed_user_effective_ids):
    """Return the projects where the user has a role.

    Args:
      viewed_user_effective_ids: list of IDs of the user whose projects we want
          to see.

    Returns:
      A triple with projects where the user is an owner, a member or a
      contributor.
    """
    with self.mc.profiler.Phase(
        'Finding roles in all projects for %r' % viewed_user_effective_ids):
      project_ids = self.services.project.GetUserRolesInAllProjects(
          self.mc.cnxn, viewed_user_effective_ids)

    owner_projects = self.GetProjects(project_ids[0])
    member_projects = self.GetProjects(project_ids[1])
    contrib_projects = self.GetProjects(project_ids[2])

    return owner_projects, member_projects, contrib_projects

  def GetUserProjects(self, viewed_user_effective_ids):
    """Get the projects to display in the user's profile.

    Args:
      viewed_user_effective_ids: set of int user IDs of the user being viewed.

    Returns:
      A 4-tuple of lists of PBs:
        - live projects the viewed user owns
        - archived projects the viewed user owns
        - live projects the viewed user is a member of
        - live projects the viewed user is a contributor to

      Any projects the viewing user should not be able to see are filtered out.
      Admins can see everything, while other users can see all non-locked
      projects they own or are a member of, as well as all live projects.
    """
    # Permissions are checked in we.GetUserRolesInAllProjects()
    owner_projects, member_projects, contrib_projects = (
        self.GetUserRolesInAllProjects(viewed_user_effective_ids))

    # We filter out DELETABLE projects, and keep a project where the user has a
    # highest role, e.g. if the user is both an owner and a member, the project
    # is listed under owner projects, not under member_projects.
    archived_projects = [
        project
        for project in owner_projects.itervalues()
        if project.state == project_pb2.ProjectState.ARCHIVED]

    contrib_projects = [
        project
        for pid, project in contrib_projects.iteritems()
        if pid not in owner_projects
        and pid not in member_projects
        and project.state != project_pb2.ProjectState.DELETABLE
        and project.state != project_pb2.ProjectState.ARCHIVED]

    member_projects = [
        project
        for pid, project in member_projects.iteritems()
        if pid not in owner_projects
        and project.state != project_pb2.ProjectState.DELETABLE
        and project.state != project_pb2.ProjectState.ARCHIVED]

    owner_projects = [
        project
        for pid, project in owner_projects.iteritems()
        if project.state != project_pb2.ProjectState.DELETABLE
        and project.state != project_pb2.ProjectState.ARCHIVED]

    by_name = lambda project: project.project_name
    owner_projects = sorted(owner_projects, key=by_name)
    archived_projects = sorted(archived_projects, key=by_name)
    member_projects = sorted(member_projects, key=by_name)
    contrib_projects = sorted(contrib_projects, key=by_name)

    return owner_projects, archived_projects, member_projects, contrib_projects

  def UpdateProject(
      self, project_id, summary=None, description=None,
      state=None, state_reason=None, access=None, issue_notify_address=None,
      attachment_bytes_used=None, attachment_quota=None, moved_to=None,
      process_inbound_email=None, only_owners_remove_restrictions=None,
      read_only_reason=None, cached_content_timestamp=None,
      only_owners_see_contributors=None, delete_time=None,
      recent_activity=None, revision_url_format=None, home_page=None,
      docs_url=None, source_url=None, logo_gcs_id=None, logo_file_name=None):
    """Update the DB with the given project information."""
    project = self.GetProject(project_id)
    self._AssertPermInProject(permissions.EDIT_PROJECT, project)

    with self.mc.profiler.Phase('updating project %r' % project_id):
      self.services.project.UpdateProject(
          self.mc.cnxn, project_id, summary=summary, description=description,
          state=state, state_reason=state_reason, access=access,
          issue_notify_address=issue_notify_address,
          attachment_bytes_used=attachment_bytes_used,
          attachment_quota=attachment_quota, moved_to=moved_to,
          process_inbound_email=process_inbound_email,
          only_owners_remove_restrictions=only_owners_remove_restrictions,
          read_only_reason=read_only_reason,
          cached_content_timestamp=cached_content_timestamp,
          only_owners_see_contributors=only_owners_see_contributors,
          delete_time=delete_time, recent_activity=recent_activity,
          revision_url_format=revision_url_format, home_page=home_page,
          docs_url=docs_url, source_url=source_url,
          logo_gcs_id=logo_gcs_id, logo_file_name=logo_file_name)

  def DeleteProject(self, project_id):
    """Mark the project as deletable.  It will be reaped by a cron job.

    Args:
      project_id: int ID of the project to delete.

    Returns:
      Nothing.

    Raises:
      NoSuchProjectException: There is no project with that ID.
    """
    project = self.GetProject(project_id)
    self._AssertPermInProject(permissions.EDIT_PROJECT, project)

    with self.mc.profiler.Phase('marking deletable %r' % project_id):
      _project = self.GetProject(project_id)
      self.services.project.MarkProjectDeletable(
          self.mc.cnxn, project_id, self.services.config)

  def StarProject(self, project_id, starred):
    """Star or unstar the specified project.

    Args:
      project_id: int ID of the project to star/unstar.
      starred: true to add a star, false to remove it.

    Returns:
      Nothing.

    Raises:
      NoSuchProjectException: There is no project with that ID.
    """
    project = self.GetProject(project_id)
    self._AssertPermInProject(permissions.SET_STAR, project)

    with self.mc.profiler.Phase('(un)starring project %r' % project_id):
      self.services.project_star.SetStar(
          self.mc.cnxn, project_id, self.mc.auth.user_id, starred)

  def IsProjectStarred(self, project_id):
    """Return True if the current user has starred the given project.

    Args:
      project_id: int ID of the project to check.

    Returns:
      True if starred.

    Raises:
      NoSuchProjectException: There is no project with that ID.
    """
    if project_id is None:
      raise exceptions.InputException('No project specified')

    if not self.mc.auth.user_id:
      return False

    with self.mc.profiler.Phase('checking project star %r' % project_id):
      # Make sure the project exists and user has permission to see it.
      _project = self.GetProject(project_id)
      return self.services.project_star.IsItemStarredBy(
        self.mc.cnxn, project_id, self.mc.auth.user_id)

  def GetProjectStarCount(self, project_id):
    """Return the number of times the project has been starred.

    Args:
      project_id: int ID of the project to check.

    Returns:
      The number of times the project has been starred.

    Raises:
      NoSuchProjectException: There is no project with that ID.
    """
    if project_id is None:
      raise exceptions.InputException('No project specified')

    with self.mc.profiler.Phase('counting stars for project %r' % project_id):
      # Make sure the project exists and user has permission to see it.
      _project = self.GetProject(project_id)
      return self.services.project_star.CountItemStars(self.mc.cnxn, project_id)

  def ListStarredProjects(self, viewed_user_id=None):
    """Return a list of projects starred by the current or viewed user.

    Args:
      viewed_user_id: optional user ID for another user's profile page, if
          not supplied, the signed in user is used.

    Returns:
      A list of projects that were starred by current user and that they
      are currently allowed to view.
    """
    # Note: No permission checks for this call, but the list of starred
    # projects is filtered based on permission to view.

    if viewed_user_id is None:
      if self.mc.auth.user_id:
        viewed_user_id = self.mc.auth.user_id
      else:
        return []  # Anon user and no viewed user specified.
    with self.mc.profiler.Phase('ListStarredProjects for %r' % viewed_user_id):
      viewable_projects = sitewide_helpers.GetViewableStarredProjects(
          self.mc.cnxn, self.services, viewed_user_id,
          self.mc.auth.effective_ids, self.mc.auth.user_pb)
    return viewable_projects

  def GetProjectConfigs(self, project_ids, use_cache=True):
    """Return the specifed configs.

    Args:
      project_ids: int IDs of the projects to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified configs.
    """
    with self.mc.profiler.Phase('getting configs for %r' % project_ids):
      configs = self.services.config.GetProjectConfigs(
          self.mc.cnxn, project_ids, use_cache=use_cache)

    projects = self._FilterVisibleProjectsDict(self.GetProjects(configs.keys()))
    configs = {project_id: configs[project_id] for project_id in projects}

    return configs

  def GetProjectConfig(self, project_id, use_cache=True):
    """Return the specifed config.

    Args:
      project_name: string name of the project to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified config.

    Raises:
      NoSuchProjectException: There is no matching config.
    """
    configs = self.GetProjectConfigs([project_id], use_cache)
    if not configs:
      raise exceptions.NoSuchProjectException()
    return configs[project_id]

  # FUTURE: labels, statuses, fields, components, rules, templates, and views.
  # FUTURE: project saved queries.
  # FUTURE: GetProjectPermissionsForUser()

  ### Issue methods

  def CreateIssue(
      self, project_id, summary, status, owner_id, cc_ids, labels,
      field_values, component_ids, marked_description, blocked_on=None,
      blocking=None, attachments=None, phases=None, approval_values=None):
    """Create and store a new issue with all the given information.

    Args:
      project_id: int ID for the current project.
      summary: one-line summary string summarizing this issue.
      status: string issue status value.  E.g., 'New'.
      owner_id: user ID of the issue owner.
      cc_ids: list of user IDs for users to be CC'd on changes.
      labels: list of label strings.  E.g., 'Priority-High'.
      field_values: list of FieldValue PBs.
      component_ids: list of int component IDs.
      marked_description: issue description with initial HTML markup.
      blocked_on: list of issue_ids that this issue is blocked on.
      blocking: list of issue_ids that this issue blocks.
      attachments: [(filename, contents, mimetype),...] attachments uploaded at
          the time the comment was made.
      phases: list of Phase PBs.
      approval_values: list of ApprovalValue PBs.

    Returns:
      A tuple (newly created Issue, Comment PB for the description).
    """
    project = self.GetProject(project_id)
    self._AssertPermInProject(permissions.CREATE_ISSUE, project)

    with self.mc.profiler.Phase('creating issue in project %r' % project_id):
      reporter_id = self.mc.auth.user_id
      new_local_id, comment = self.services.issue.CreateIssue(
          self.mc.cnxn, self.services, project_id, summary, status,
          owner_id, cc_ids, labels, field_values, component_ids, reporter_id,
          marked_description, blocked_on=blocked_on, blocking=blocking,
          attachments=attachments, index_now=False, phases=phases,
          approval_values=approval_values)
      logging.info('created issue %r in project %r', new_local_id, project_id)

    with self.mc.profiler.Phase('following up after issue creation'):
      self.services.project.UpdateRecentActivity(self.mc.cnxn, project_id)
      new_issue = self.services.issue.GetIssueByLocalID(
          self.mc.cnxn, project_id, new_local_id)

    return new_issue, comment

  def ListIssues(self, query_string, query_project_names, me_user_id,
                 items_per_page, paginate_start, url_params, can,
                 group_by_spec, sort_spec, use_cached_searches,
                 display_mode=None, project=None):
    """Do an issue search w/ mc + passed in args to return a pipeline object."""
    # Permission to view a project is checked in Frontendsearchpipeline().
    # Individual results are filtered by permissions in SearchForIIDs().

    with self.mc.profiler.Phase('searching issues'):
      pipeline = frontendsearchpipeline.FrontendSearchPipeline(
          self.mc.cnxn, self.services, self.mc.auth, me_user_id,
          query_string, query_project_names, items_per_page, paginate_start,
          url_params, can, group_by_spec, sort_spec, self.mc.warnings,
          self.mc.errors, use_cached_searches, self.mc.profiler,
          display_mode=display_mode, project=project)
      if not self.mc.errors.AnyErrors():
        pipeline.SearchForIIDs()
        pipeline.MergeAndSortIssues()
        pipeline.Paginate()
      # TODO(jojwang): raise InvalidQueryException.
      return pipeline

  # TODO(jrobbins): This method also requires self.mc to be a MonorailRequest.
  def FindIssuePositionInSearch(self, issue):
    """Do an issue search and return flipper info for the given issue.

    Args:
      issue: issue that the user is currently viewing.

    Returns:
      A 4-tuple of flipper info: (prev_iid, cur_index, next_iid, total_count).
    """
    # Permission to view a project is checked in Frontendsearchpipeline().
    # Individual results are filtered by permissions in SearchForIIDs().

    with self.mc.profiler.Phase('finding issue position in search'):
      url_params = [(name, self.mc.GetParam(name)) for name in
                    framework_helpers.RECOGNIZED_PARAMS]
      pipeline = frontendsearchpipeline.FrontendSearchPipeline(
           self.mc.cnxn, self.services, self.mc.auth, self.mc.me_user_id,
           self.mc.query, self.mc.query_project_names, self.mc.num,
           self.mc.start, url_params, self.mc.can, self.mc.group_by_spec,
           self.mc.sort_spec, self.mc.warnings, self.mc.errors,
           self.mc.use_cached_searches, self.mc.profiler,
           display_mode=self.mc.mode, project=self.mc.project)
      if not self.mc.errors.AnyErrors():
        # Only do the search if the user's query parsed OK.
        pipeline.SearchForIIDs()

      # Note: we never call MergeAndSortIssues() because we don't need a unified
      # sorted list, we only need to know the position on such a list of the
      # current issue.
      prev_iid, cur_index, next_iid = pipeline.DetermineIssuePosition(issue)
      return prev_iid, cur_index, next_iid, pipeline.total_count

  def GetIssuesDict(self, issue_ids, use_cache=True,
                    allow_viewing_deleted=False):
    """Return the specified issue.

    Args:
      issue_ids: int global issue IDs.
      use_cache: set to false to ensure fresh issues.
      allow_viewing_deleted: set to true to allow user to view deleted issues.

    Returns:
      The requested Issue PBs.
    """
    with self.mc.profiler.Phase('getting issues %r' % issue_ids):
      issues = self.services.issue.GetIssuesDict(
          self.mc.cnxn, issue_ids, use_cache=use_cache)

    if len(issues) != len(set(issue_ids)):
      raise exceptions.NoSuchIssueException()

    issues = {
        issue_id: issue
        for issue_id, issue in issues.iteritems()
        if self._UserCanViewIssue(issue, allow_viewing_deleted)[-1]}
    return issues

  def GetIssue(self, issue_id, use_cache=True, allow_viewing_deleted=False):
    """Return the specified issue.

    Args:
      issue_id: int global issue ID.
      use_cache: set to false to ensure fresh issue.
      allow_viewing_deleted: set to true to allow user to view a deleted issue.

    Returns:
      The requested Issue PB.
    """
    if issue_id is None:
      raise exceptions.InputException('No issue issue_id specified')

    with self.mc.profiler.Phase('getting issue %r' % issue_id):
      issue = self.services.issue.GetIssue(
          self.mc.cnxn, issue_id, use_cache=use_cache)

    self._AssertUserCanViewIssue(
        issue, allow_viewing_deleted=allow_viewing_deleted)
    return issue

  def ListReferencedIssues(self, ref_tuples, default_project_name):
    """Return the specified issues."""
    ref_tuples = list(set(ref_tuples))
    ref_projects = self.services.project.GetProjectsByName(
        self.mc.cnxn,
        [(ref_pn or default_project_name) for ref_pn, _ in ref_tuples])
    issue_ids, _misses = self.services.issue.ResolveIssueRefs(
        self.mc.cnxn, ref_projects, default_project_name, ref_tuples)
    open_issues, closed_issues = (
        tracker_helpers.GetAllowedOpenedAndClosedIssues(
            self.mc, issue_ids, self.services))
    return open_issues, closed_issues

  def GetIssueByLocalID(
      self, project_id, local_id, use_cache=True,
      allow_viewing_deleted=False):
    """Return the specified issue, TODO: iff the signed in user may view it.

    Args:
      project_id: int project ID of the project that contains the issue.
      local_id: int issue local id number.
      use_cache: set to False when doing read-modify-write operations.
      allow_viewing_deleted: set to True to return a deleted issue so that
          an authorized user may undelete it.

    Returns:
      The specified Issue PB.

    Raises:
      exceptions.InputException: Something was not specified properly.
      exceptions.NoSuchIssueException: The issue does not exist.
    """
    if project_id is None:
      raise exceptions.InputException('No project specified')
    if local_id is None:
      raise exceptions.InputException('No issue local_id specified')

    with self.mc.profiler.Phase('getting issue %r:%r' % (project_id, local_id)):
      issue = self.services.issue.GetIssueByLocalID(
          self.mc.cnxn, project_id, local_id, use_cache=use_cache)

    self._AssertUserCanViewIssue(
        issue, allow_viewing_deleted=allow_viewing_deleted)
    return issue

  def GetRelatedIssueRefs(self, issues):
    """Return a dict {iid: (project_name, local_id)} for all related issues."""
    related_iids = set()
    with self.mc.profiler.Phase('getting related issue refs'):
      for issue in issues:
        related_iids.update(issue.blocked_on_iids)
        related_iids.update(issue.blocking_iids)
        if issue.merged_into:
          related_iids.add(issue.merged_into)
      logging.info('related_iids is %r', related_iids)
      return self.services.issue.LookupIssueRefs(self.mc.cnxn, related_iids)

  def UpdateIssueApproval(self, issue_id, approval_id, approval_delta,
                          comment_content, is_description, attachments=None):
    """Update an issue's approval."""

    issue, approval_value = self.services.issue.GetIssueApproval(
        self.mc.cnxn, issue_id, approval_id)

    self._AssertPermInIssue(issue, permissions.EDIT_ISSUE)
    project = self.GetProject(issue.project_id)
    config = self.GetProjectConfig(issue.project_id)

    if attachments:
      with self.mc.profiler.Phase('Accounting for quota'):
        new_bytes_used = tracker_helpers.ComputeNewQuotaBytesUsed(
          project, attachments)
        self.services.project.UpdateProject(
          self.mc.cnxn, issue.project_id, attachment_bytes_used=new_bytes_used)

    if approval_delta.status:
      if not permissions.CanUpdateApprovalStatus(
          self.mc.auth.effective_ids, approval_value.approver_ids,
          approval_value.status, approval_delta.status):
        raise permissions.PermissionException(
            'User not allowed to make this status update.')

    if approval_delta.approver_ids_remove or approval_delta.approver_ids_add:
      if not permissions.CanUpdateApprovers(
          self.mc.auth.effective_ids, approval_value.approver_ids):
        raise permissions.PermissionException(
            'User not allowed to modify approvers of this approval.')

    with self.mc.profiler.Phase(
        'updating approval for issue %r, aprpoval %r' % (
            issue_id, approval_id)):
      comment_pb = self.services.issue.DeltaUpdateIssueApproval(
          self.mc.cnxn, self.mc.auth.user_id, config, issue, approval_value,
          approval_delta, comment_content=comment_content,
          is_description=is_description, attachments=attachments)
      send_notifications.PrepareAndSendApprovalChangeNotification(
          issue_id, approval_id, framework_helpers.GetHostPort(), comment_pb.id)

    return approval_value, comment_pb

  def UpdateIssue(
      self, issue, delta, comment_content, attachments=None, send_email=True,
      is_description=False):
    """Update an issue with a set of changes and add a comment.

    Args:
      issue: Existing Issue PB for the issue to be modified.
      delta: IssueDelta object containing all the changes to be made.
      comment_content: string content of the user's comment.
      attachments: List [(filename, contents, mimetype),...] of attachments.
      send_email: set to False to suppress email notifications.
      is_description: True if this adds a new issue description.

    Returns:
      Nothing.
    """
    project = self.GetProject(issue.project_id)
    self._AssertPermInIssue(issue, permissions.EDIT_ISSUE)
    config = self.GetProjectConfig(issue.project_id)
    old_owner_id = tracker_bizobj.GetOwnerId(issue)

    if attachments:
      with self.mc.profiler.Phase('Accounting for quota'):
        new_bytes_used = tracker_helpers.ComputeNewQuotaBytesUsed(
          project, attachments)
        self.services.project.UpdateProject(
          self.mc.cnxn, issue.project_id, attachment_bytes_used=new_bytes_used)

    with self.mc.profiler.Phase('Updating issue %r' % (issue.issue_id)):
      _amendments, comment_pb = self.services.issue.DeltaUpdateIssue(
          self.mc.cnxn, self.services, self.mc.auth.user_id, issue.project_id,
          config, issue, delta, comment=comment_content,
          attachments=attachments, is_description=is_description)

    with self.mc.profiler.Phase('Following up after issue update'):
      # TODO(jrobbins): side effects of setting merged_into.
      self.services.project.UpdateRecentActivity(
          self.mc.cnxn, issue.project_id)

    with self.mc.profiler.Phase('Generating notifications'):
      if comment_pb:
        hostport = framework_helpers.GetHostPort()
        reporter_id = self.mc.auth.user_id
        send_notifications.PrepareAndSendIssueChangeNotification(
            issue.issue_id, hostport, reporter_id,
            send_email=send_email, old_owner_id=old_owner_id,
            comment_id=comment_pb.id)

  def DeleteIssue(self, issue, delete):
    """Mark or unmark the given issue as deleted."""
    self._AssertPermInIssue(issue, permissions.DELETE_ISSUE)

    with self.mc.profiler.Phase('Marking issue %r deleted' % (issue.issue_id)):
      self.services.issue.SoftDeleteIssue(
          self.mc.cnxn, issue.project_id, issue.local_id, delete,
          self.services.user)

  # TODO(jrobbins): This method also requires self.mc to be a MonorailRequest.
  def GetIssuePositionInHotlist(self, current_issue, hotlist):
    """Get index info of an issue within a hotlist.

    Args:
      current_issue: the currently viewed issue.
      hotlist: the hotlist this flipper is flipping through.
    """
    issues_list = self.services.issue.GetIssues(self.mc.cnxn,
        [item.issue_id for item in hotlist.items])
    project_ids = hotlist_helpers.GetAllProjectsOfIssues(
        [issue for issue in issues_list])
    config_list = hotlist_helpers.GetAllConfigsOfProjects(
        self.mc.cnxn, project_ids, self.services)
    harmonized_config = tracker_bizobj.HarmonizeConfigs(config_list)
    mr = self.mc  # TODO(jrobbins): change GetSortedHotlistIssues.
    (sorted_issues, _hotlist_issues_context,
     _users) = hotlist_helpers.GetSortedHotlistIssues(
         mr, hotlist.items, issues_list, harmonized_config,
         self.services)
    (prev_iid, cur_index,
     next_iid) = features_bizobj.DetermineHotlistIssuePosition(
         current_issue, [issue.issue_id for issue in sorted_issues])
    total_count = len(sorted_issues)
    return prev_iid, cur_index, next_iid, total_count

  # FUTURE: GetIssuePermissionsForUser()

  # FUTURE: CreateComment()

  def ListIssueComments(self, issue):
    """Return comments on the specified viewable issue."""
    self._AssertUserCanViewIssue(issue)

    with self.mc.profiler.Phase('getting comments for %r' % issue.issue_id):
      comments = self.services.issue.GetCommentsForIssue(
          self.mc.cnxn, issue.issue_id)
    return comments

  # FUTURE: UpdateComment()

  def DeleteComment(self, issue, comment, delete):
    """Mark or unmark a comment as deleted by the current user."""
    self._AssertUserCanViewIssue(issue)

    project = self.GetProject(issue.project_id)
    config = self.GetProjectConfig(issue.project_id)
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, self.mc.auth.effective_ids, config)
    if ((comment.is_spam and self.mc.auth.user_id == comment.user_id) or
        not permissions.CanDelete(
            self.mc.auth.user_id, self.mc.auth.effective_ids, self.mc.perms,
            comment.deleted_by, comment.user_id, project,
            permissions.GetRestrictions(issue), granted_perms=granted_perms)):
      raise permissions.PermissionException('Cannot delete comment')

    with self.mc.profiler.Phase(
        'deleting issue %r comment %r' % (issue.issue_id, comment.id)):
      self.services.issue.SoftDeleteComment(
          self.mc.cnxn, issue, comment, self.mc.auth.user_id,
          self.services.user, delete=delete)

  def StarIssue(self, issue, starred):
    """Set or clear a star on the given issue for the signed in user."""
    if not self.mc.auth.user_id:
      raise permissions.PermissionException('Anon cannot star issues')
    self._AssertPermInIssue(issue, permissions.SET_STAR)

    with self.mc.profiler.Phase('starring issue %r' % issue.issue_id):
      config = self.services.config.GetProjectConfig(
          self.mc.cnxn, issue.project_id)
      self.services.issue_star.SetStar(
          self.mc.cnxn, self.services, config, issue.issue_id,
          self.mc.auth.user_id, starred)

  def IsIssueStarred(self, issue, cnxn=None):
    """Return True if the given issue is starred by the signed in user."""
    self._AssertUserCanViewIssue(issue)

    with self.mc.profiler.Phase('checking star %r' % issue.issue_id):
      return self.services.issue_star.IsItemStarredBy(
          cnxn or self.mc.cnxn, issue.issue_id, self.mc.auth.user_id)

  def ListStarredIssueIDs(self):
    """Return a list of the issue IDs that the current issue has starred."""
    # This returns an unfiltered list of issue_ids.  Permissions will be
    # applied if and when the caller attempts to load each issue.

    with self.mc.profiler.Phase('getting stars %r' % self.mc.auth.user_id):
      return self.services.issue_star.LookupStarredItemIDs(
          self.mc.cnxn, self.mc.auth.user_id)

  def SnapshotCountsQuery(self, project, timestamp, group_by, label_prefix=None,
                          query=None, canned_query=None):
    """Query IssueSnapshots for daily counts.

    See chart_svc.QueryIssueSnapshots for more detail on arguments.

    Args:
      project (Project): Project to search.
      timestamp (int): Will query for snapshots at this timestamp.
      group_by (str): 2nd dimension, see QueryIssueSnapshots for options.
      label_prefix (str): Required for label queries. Only returns results
        with the supplied prefix.
      query (str, optional): If supplied, will parse & apply query conditions.
      canned_query (str, optional): Value derived from the can= query parameter.

    Returns:
      1. A dict of {name: count} for each item in group_by.
      2. A list of any unsupported query conditions in query.
    """
    # This returns counts of viewable issues.

    with self.mc.profiler.Phase('querying snapshot counts'):
      return self.services.chart.QueryIssueSnapshots(
        self.mc.cnxn, self.services, timestamp, self.mc.auth.effective_ids,
        project, self.mc.perms, group_by=group_by,
        label_prefix=label_prefix, query=query, canned_query=canned_query)

  ### User methods

  def GetMemberships(self, user_id):
    """Return the user group ids for the given user visible to the requester."""
    group_ids = self.services.usergroup.LookupMemberships(self.mc.cnxn, user_id)
    if user_id == self.mc.auth.user_id:
      return group_ids
    (member_ids_by_ids, owner_ids_by_ids
    ) = self.services.usergroup.LookupAllMembers(
        self.mc.cnxn, group_ids)
    settings_by_id = self.services.usergroup.GetAllGroupSettings(
        self.mc.cnxn, group_ids)

    (owned_project_ids, membered_project_ids,
     contrib_project_ids) = self.services.project.GetUserRolesInAllProjects(
         self.mc.cnxn, self.mc.auth.effective_ids)
    project_ids = owned_project_ids.union(
        membered_project_ids).union(contrib_project_ids)

    visible_group_ids = []
    for group_id, settings in settings_by_id.items():
      member_ids = member_ids_by_ids.get(group_id)
      owner_ids = owner_ids_by_ids.get(group_id)
      if permissions.CanViewGroupMembers(
          self.mc.perms, self.mc.auth.effective_ids, settings, member_ids,
          owner_ids, project_ids):
        visible_group_ids.append(group_id)

    return visible_group_ids

  def ListReferencedUsers(self, emails):
    """Return a of the given emails' User PBs."""
    with self.mc.profiler.Phase('getting existing users'):
      user_id_dict = self.services.user.LookupExistingUserIDs(
          self.mc.cnxn, emails)
      users_by_id = self.services.user.GetUsersByIDs(
          self.mc.cnxn, user_id_dict.values())
    return users_by_id.values()

  def StarUser(self, user_id, starred):
    """Star or unstar the specified user.

    Args:
      user_id: int ID of the user to star/unstar.
      starred: true to add a star, false to remove it.

    Returns:
      Nothing.

    Raises:
      NoSuchUserException: There is no user with that ID.
    """
    if not self.mc.auth.user_id:
      raise exceptions.InputException('No current user specified')

    with self.mc.profiler.Phase('(un)starring user %r' % user_id):
      # Make sure the user exists and user has permission to see it.
      self.services.user.LookupUserEmail(self.mc.cnxn, user_id)
      self.services.user_star.SetStar(
          self.mc.cnxn, user_id, self.mc.auth.user_id, starred)

  def IsUserStarred(self, user_id):
    """Return True if the current user has starred the given user.

    Args:
      user_id: int ID of the user to check.

    Returns:
      True if starred.

    Raises:
      NoSuchUserException: There is no user with that ID.
    """
    if user_id is None:
      raise exceptions.InputException('No user specified')

    if not self.mc.auth.user_id:
      return False

    with self.mc.profiler.Phase('checking user star %r' % user_id):
      # Make sure the user exists.
      self.services.user.LookupUserEmail(self.mc.cnxn, user_id)
      return self.services.user_star.IsItemStarredBy(
        self.mc.cnxn, user_id, self.mc.auth.user_id)

  def GetUserStarCount(self, user_id):
    """Return the number of times the user has been starred.

    Args:
      user_id: int ID of the user to check.

    Returns:
      The number of times the user has been starred.

    Raises:
      NoSuchUserException: There is no user with that ID.
    """
    if user_id is None:
      raise exceptions.InputException('No user specified')

    with self.mc.profiler.Phase('counting stars for user %r' % user_id):
      # Make sure the user exists.
      self.services.user.LookupUserEmail(self.mc.cnxn, user_id)
      return self.services.user_star.CountItemStars(self.mc.cnxn, user_id)

  # FUTURE: GetUser()
  # FUTURE: UpdateUser()
  # FUTURE: DeleteUser()
  # FUTURE: ListStarredUsers()

  def GetUserCommits(self, user_id, from_timestamp, to_timestamp):
    """Return a user's commits given their user id or email.

    Args:
      user_id: int user ID.

    Returns:
      A list of commits from the given user.

    Raises:
      exceptions.InputException: User was not specified properly.
    """
    if user_id is None:
      raise exceptions.InputException('No user specified')

    author_id = self.services.user.LookupUserID(
        self.mc.cnxn, user_id, autocreate=True)

    with self.mc.profiler.Phase('getting user commits of %r' % (user_id)):
      commits = self.services.user.GetUserCommits(
          self.mc.cnxn, author_id, from_timestamp, to_timestamp)

    return commits

  ### Group methods

  # FUTURE: CreateGroup()
  # FUTURE: ListGroups()
  # FUTURE: UpdateGroup()
  # FUTURE: DeleteGroup()

  ### Hotlist methods

  def CreateHotlist(
      self, name, summary, description, editor_ids, issue_ids, is_private):
    """Create a hotlist.

    Args:
      name: a valid hotlist name.
      summary: one-line explanation of the hotlist.
      description: one-page explanation of the hotlist.
      editor_ids: a list of user IDs for the hotlist editors.
      issue_ids: a list of issue IDs for the hotlist issues.
      is_private: True if the hotlist can only be viewed by owners and editors.

    Returns:
      The newly created hotlist.

    Raises:
      HotlistAlreadyExists: A hotlist with the given name already exists.
      InputException: No user is signed in or the proposed name is invalid.
    """
    if not self.mc.auth.user_id:
      raise exceptions.InputException('Anon cannot create hotlists.')

    with self.mc.profiler.Phase('creating hotlist %s' % name):
      hotlist = self.services.features.CreateHotlist(
          self.mc.cnxn, name, summary, description, [self.mc.auth.user_id],
          editor_ids, issue_ids, is_private, ts=int(time.time()))

    return hotlist

  def GetHotlist(self, hotlist_id, use_cache=True):
    """Return the specified hotlist.

    Args:
      hotlist_id: int hotlist_id of the hotlist to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified hotlist.

    Raises:
      NoSuchHotlistException: There is no hotlist with that ID.
    """
    if hotlist_id is None:
      raise exceptions.InputException('No hotlist specified')

    with self.mc.profiler.Phase('getting hotlist %r' % hotlist_id):
      hotlist = self.services.features.GetHotlist(
          self.mc.cnxn, hotlist_id, use_cache=use_cache)
    self._AssertUserCanViewHotlist(hotlist)
    return hotlist

  def ListHotlistsByUser(self, user_id):
    """Return the hotlists for the given user.

    Args:
      user_id (int): The id of the user to query.

    Returns:
      The hotlists for the given user.
    """
    if user_id is None:
      raise exceptions.InputException('No user specified')

    with self.mc.profiler.Phase('querying hotlists for user %r' % user_id):
      hotlists = self.services.features.GetHotlistsByUserID(
          self.mc.cnxn, user_id)

    # Filter the hotlists that the currently authenticated user cannot see.
    result = [
        hotlist
        for hotlist in hotlists
        if permissions.CanViewHotlist(self.mc.auth.effective_ids, hotlist)]
    return result

  def ListHotlistsByIssue(self, issue_id):
    """Return the hotlists the given issue is part of.

    Args:
      issue_id (int): The id of the issue to query.

    Returns:
      The hotlists the given issue is part of.
    """
    # Check that the issue exists and the user has permission to see it.
    self.GetIssue(issue_id)

    with self.mc.profiler.Phase('querying hotlists for issue %r' % issue_id):
      hotlists = self.services.features.GetHotlistsByIssueID(
          self.mc.cnxn, issue_id)

    # Filter the hotlists that the currently authenticated user cannot see.
    result = [
        hotlist
        for hotlist in hotlists
        if permissions.CanViewHotlist(self.mc.auth.effective_ids, hotlist)]
    return result

  def ListRecentlyVisitedHotlists(self):
    """Return the recently visited hotlists for the logged in user.

    Returns:
      The recently visited hotlists for the given user, or an empty list if no
      user is logged in.
    """
    if not self.mc.auth.user_id:
      return []

    with self.mc.profiler.Phase(
        'get recently visited hotlists for user %r' % self.mc.auth.user_id):
      hotlist_ids = self.services.user.GetRecentlyVisitedHotlists(
          self.mc.cnxn, self.mc.auth.user_id)
      hotlists_by_id = self.services.features.GetHotlists(
          self.mc.cnxn, hotlist_ids)
      hotlists = [hotlists_by_id[hotlist_id] for hotlist_id in hotlist_ids]

    # Filter the hotlists that the currently authenticated user cannot see.
    # It might be that some of the hotlists have become private since the user
    # last visited them, or the user has lost access for other reasons.
    result = [
        hotlist
        for hotlist in hotlists
        if permissions.CanViewHotlist(self.mc.auth.effective_ids, hotlist)]
    return result

  def StarHotlist(self, hotlist_id, starred):
    """Star or unstar the specified hotlist.

    Args:
      hotlist_id: int ID of the hotlist to star/unstar.
      starred: true to add a star, false to remove it.

    Returns:
      Nothing.

    Raises:
      NoSuchHotlistException: There is no hotlist with that ID.
    """
    if hotlist_id is None:
      raise exceptions.InputException('No hotlist specified')

    if not self.mc.auth.user_id:
      raise exceptions.InputException('No current user specified')

    with self.mc.profiler.Phase('(un)starring hotlist %r' % hotlist_id):
      # Make sure the hotlist exists and user has permission to see it.
      self.GetHotlist(hotlist_id)
      self.services.hotlist_star.SetStar(
          self.mc.cnxn, hotlist_id, self.mc.auth.user_id, starred)

  def IsHotlistStarred(self, hotlist_id):
    """Return True if the current hotlist has starred the given hotlist.

    Args:
      hotlist_id: int ID of the hotlist to check.

    Returns:
      True if starred.

    Raises:
      NoSuchHotlistException: There is no hotlist with that ID.
    """
    if hotlist_id is None:
      raise exceptions.InputException('No hotlist specified')

    if not self.mc.auth.user_id:
      return False

    with self.mc.profiler.Phase('checking hotlist star %r' % hotlist_id):
      # Make sure the hotlist exists and user has permission to see it.
      self.GetHotlist(hotlist_id)
      return self.services.hotlist_star.IsItemStarredBy(
        self.mc.cnxn, hotlist_id, self.mc.auth.user_id)

  def GetHotlistStarCount(self, hotlist_id):
    """Return the number of times the hotlist has been starred.

    Args:
      hotlist_id: int ID of the hotlist to check.

    Returns:
      The number of times the hotlist has been starred.

    Raises:
      NoSuchHotlistException: There is no hotlist with that ID.
    """
    if hotlist_id is None:
      raise exceptions.InputException('No hotlist specified')

    with self.mc.profiler.Phase('counting stars for hotlist %r' % hotlist_id):
      # Make sure the hotlist exists and user has permission to see it.
      self.GetHotlist(hotlist_id)
      return self.services.hotlist_star.CountItemStars(self.mc.cnxn, hotlist_id)

  def CheckHotlistName(self, name):
    """Check that a hotlist name is valid and not already in use.

    Args:
      name: str the hotlist name to check.

    Returns:
      None if the user can create a hotlist with that name, or a string with the
      reason the name can't be used.

    Raises:
      InputException: The user is not signed in.
    """
    if not self.mc.auth.user_id:
      raise exceptions.InputException('No current user specified')

    with self.mc.profiler.Phase('checking hotlist name: %r' % name):
      if not framework_bizobj.IsValidHotlistName(name):
        return '%s is not a valid hotlist name.' % name
      if self.services.features.LookupHotlistIDs(
          self.mc.cnxn, [name], [self.mc.auth.user_id]):
        return 'There is already a hotlist with that name.'

    return None

  def RemoveIssuesFromHotlists(self, hotlist_ids, issue_ids):
    """Remove the issues given in issue_ids from the given hotlists.

    Args:
      hotlist_ids: a list of hotlist ids to remove the issues from.
      issue_ids: a list of issue_ids to be removed.

    Raises:
      PermissionException: The user has no permission to edit the hotlist.
      NoSuchHotlistException: One of the hotlist ids was not found.
    """
    for hotlist_id in hotlist_ids:
      self._AssertUserCanEditHotlist(self.GetHotlist(hotlist_id))

    with self.mc.profiler.Phase(
        'Removing issues %r from hotlists %r' % (issue_ids, hotlist_ids)):
      self.services.features.RemoveIssuesFromHotlists(
          self.mc.cnxn, hotlist_ids, issue_ids, self.services.issue,
          self.services.chart)

  def AddIssuesToHotlists(self, hotlist_ids, issue_ids, note):
    """Add the issues given in issue_ids to the given hotlists.

    Args:
      hotlist_ids: a list of hotlist ids to add the issues to.
      issue_ids: a list of issue_ids to be added.
      note: a string with a message to record along with the issues.

    Raises:
      PermissionException: The user has no permission to edit the hotlist.
      NoSuchHotlistException: One of the hotlist ids was not found.
    """
    for hotlist_id in hotlist_ids:
      self._AssertUserCanEditHotlist(self.GetHotlist(hotlist_id))

    issues_to_add = [
        (issue_id, self.mc.auth.user_id, int(time.time()), note)
        for issue_id in issue_ids]

    with self.mc.profiler.Phase(
        'Removing issues %r from hotlists %r' % (issue_ids, hotlist_ids)):
      self.services.features.AddIssuesToHotlists(
          self.mc.cnxn, hotlist_ids, issues_to_add, self.services.issue,
          self.services.chart)


  # FUTURE: UpdateHotlist()
  # FUTURE: DeleteHotlist()

  def DismissCue(self, cue_id):
    """Dismiss the given cue and don't show it again to the logged in user."""
    if cue_id is None:
      raise exceptions.InputException('No cue specified')

    if not self.mc.auth.user_id:
      raise exceptions.InputException('No current user specified')

    if cue_id not in features_constants.KNOWN_CUES:
      raise exceptions.InputException('%s is not a known cue ID.')

    with self.mc.profiler.Phase('Handling user set cue request: %r' % cue_id):
      new_dismissed_cues = self.mc.auth.user_pb.dismissed_cues
      if cue_id in new_dismissed_cues:
        return
      new_dismissed_cues.append(cue_id)
      self.services.user.UpdateUserSettings(
          self.mc.cnxn, self.mc.auth.user_id, self.mc.auth.user_pb,
          dismissed_cues=new_dismissed_cues)
