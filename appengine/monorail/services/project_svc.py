# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of functions that provide persistence for projects.

This module provides functions to get, update, create, and (in some
cases) delete each type of project business object.  It provides
a logical persistence layer on top of the database.

Business objects are described in project_pb2.py.
"""

import collections
import logging
import time

import settings
from framework import framework_bizobj
from framework import permissions
from framework import sql
from services import caches
from proto import project_pb2


PROJECT_TABLE_NAME = 'Project'
USER2PROJECT_TABLE_NAME = 'User2Project'
EXTRAPERM_TABLE_NAME = 'ExtraPerm'
MEMBERNOTES_TABLE_NAME = 'MemberNotes'
USERGROUPPROJECTS_TABLE_NAME = 'Group2Project'
AUTOCOMPLETEEXCLUSION_TABLE_NAME = 'AutocompleteExclusion'

PROJECT_COLS = [
    'project_id', 'project_name', 'summary', 'description', 'state', 'access',
    'read_only_reason', 'state_reason', 'delete_time', 'issue_notify_address',
    'attachment_bytes_used', 'attachment_quota',
    'cached_content_timestamp', 'recent_activity_timestamp', 'moved_to',
    'process_inbound_email', 'only_owners_remove_restrictions',
    'only_owners_see_contributors', 'revision_url_format',
    'home_page', 'docs_url', 'source_url', 'logo_gcs_id', 'logo_file_name']
USER2PROJECT_COLS = ['project_id', 'user_id', 'role_name']
EXTRAPERM_COLS = ['project_id', 'user_id', 'perm']
MEMBERNOTES_COLS = ['project_id', 'user_id', 'notes']
AUTOCOMPLETEEXCLUSION_COLS = ['project_id', 'user_id']


class ProjectTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage both RAM and memcache for Project PBs."""

  def __init__(self, cachemanager, project_service):
    super(ProjectTwoLevelCache, self).__init__(
        cachemanager, 'project', 'project:', project_pb2.Project)
    self.project_service = project_service

  def _DeserializeProjects(
      self, project_rows, role_rows, extraperm_rows):
    """Convert database rows into a dictionary of Project PB keyed by ID."""
    project_dict = {}

    for project_row in project_rows:
      (project_id, project_name, summary, description, state_name,
       access_name, read_only_reason, state_reason, delete_time,
       issue_notify_address, attachment_bytes_used, attachment_quota, cct,
       recent_activity_timestamp, moved_to, process_inbound_email,
       oorr, oosc, revision_url_format, home_page, docs_url, source_url,
       logo_gcs_id, logo_file_name) = project_row
      project = project_pb2.Project()
      project.project_id = project_id
      project.project_name = project_name
      project.summary = summary
      project.description = description
      project.state = project_pb2.ProjectState(state_name.upper())
      project.state_reason = state_reason or ''
      project.access = project_pb2.ProjectAccess(access_name.upper())
      project.read_only_reason = read_only_reason or ''
      project.issue_notify_address = issue_notify_address or ''
      project.attachment_bytes_used = attachment_bytes_used or 0
      project.attachment_quota = attachment_quota
      project.recent_activity = recent_activity_timestamp or 0
      project.cached_content_timestamp = cct or 0
      project.delete_time = delete_time or 0
      project.moved_to = moved_to or ''
      project.process_inbound_email = bool(process_inbound_email)
      project.only_owners_remove_restrictions = bool(oorr)
      project.only_owners_see_contributors = bool(oosc)
      project.revision_url_format = revision_url_format or ''
      project.home_page = home_page or ''
      project.docs_url = docs_url or ''
      project.source_url = source_url or ''
      project.logo_gcs_id = logo_gcs_id or ''
      project.logo_file_name = logo_file_name or ''
      project_dict[project_id] = project

    for project_id, user_id, role_name in role_rows:
      project = project_dict[project_id]
      if role_name == 'owner':
        project.owner_ids.append(user_id)
      elif role_name == 'committer':
        project.committer_ids.append(user_id)
      elif role_name == 'contributor':
        project.contributor_ids.append(user_id)

    for project_id, user_id, perm in extraperm_rows:
      project = project_dict[project_id]
      extra_perms = permissions.FindExtraPerms(project, user_id)
      if not extra_perms:
        extra_perms = project_pb2.Project.ExtraPerms(
            member_id=user_id)
        project.extra_perms.append(extra_perms)

      extra_perms.perms.append(perm)

    return project_dict

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, hit the database to get missing projects."""
    project_rows = self.project_service.project_tbl.Select(
        cnxn, cols=PROJECT_COLS, project_id=keys)
    role_rows = self.project_service.user2project_tbl.Select(
        cnxn, cols=['project_id', 'user_id', 'role_name'],
        project_id=keys)
    extraperm_rows = self.project_service.extraperm_tbl.Select(
        cnxn, cols=EXTRAPERM_COLS, project_id=keys)
    retrieved_dict = self._DeserializeProjects(
        project_rows, role_rows, extraperm_rows)
    return retrieved_dict


class ProjectService(object):
  """The persistence layer for project data."""

  def __init__(self, cache_manager):
    """Initialize this module so that it is ready to use.

    Args:
      cache_manager: local cache with distributed invalidation.
    """
    self.project_tbl = sql.SQLTableManager(PROJECT_TABLE_NAME)
    self.user2project_tbl = sql.SQLTableManager(USER2PROJECT_TABLE_NAME)
    self.extraperm_tbl = sql.SQLTableManager(EXTRAPERM_TABLE_NAME)
    self.membernotes_tbl = sql.SQLTableManager(MEMBERNOTES_TABLE_NAME)
    self.usergroupprojects_tbl = sql.SQLTableManager(
        USERGROUPPROJECTS_TABLE_NAME)
    self.acexclusion_tbl = sql.SQLTableManager(
        AUTOCOMPLETEEXCLUSION_TABLE_NAME)

    # Like a dictionary {project_id: project}
    self.project_2lc = ProjectTwoLevelCache(cache_manager, self)

    # The project name to ID cache can never be invalidated by individual
    # project changes because it is keyed by strings instead of ints.  In
    # the case of rare operations like deleting a project (or a future
    # project renaming feature), we just InvalidateAll().
    self.project_names_to_ids = cache_manager.MakeCache('project')

  ### Creating projects

  def CreateProject(
      self, cnxn, project_name, owner_ids, committer_ids, contributor_ids,
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
      ProjectAlreadyExists: if a project with that name already exists.
    """
    assert framework_bizobj.IsValidProjectName(project_name)
    if self.LookupProjectIDs(cnxn, [project_name]):
      raise ProjectAlreadyExists()

    project = project_pb2.MakeProject(
        project_name, state=state, access=access,
        description=description, summary=summary,
        owner_ids=owner_ids, committer_ids=committer_ids,
        contributor_ids=contributor_ids, read_only_reason=read_only_reason,
        home_page=home_page, docs_url=docs_url, source_url=source_url,
        logo_gcs_id=logo_gcs_id, logo_file_name=logo_file_name)

    project.project_id = self._InsertProject(cnxn, project)
    return project.project_id

  def _InsertProject(self, cnxn, project):
    """Insert the given project into the database."""
    # Note: project_id is not specified because it is auto_increment.
    project_id = self.project_tbl.InsertRow(
        cnxn, project_name=project.project_name,
        summary=project.summary, description=project.description,
        state=str(project.state), access=str(project.access),
        home_page=project.home_page, docs_url=project.docs_url,
        source_url=project.source_url,
        logo_gcs_id=project.logo_gcs_id, logo_file_name=project.logo_file_name)
    logging.info('stored project was given project_id %d', project_id)

    self.user2project_tbl.InsertRows(
        cnxn, ['project_id', 'user_id', 'role_name'],
        [(project_id, user_id, 'owner')
         for user_id in project.owner_ids] +
        [(project_id, user_id, 'committer')
         for user_id in project.committer_ids] +
        [(project_id, user_id, 'contributor')
         for user_id in project.contributor_ids])

    return project_id

  ### Lookup project names and IDs

  def LookupProjectIDs(self, cnxn, project_names):
    """Return a list of project IDs for the specified projects."""
    id_dict, missed_names = self.project_names_to_ids.GetAll(project_names)
    if missed_names:
      rows = self.project_tbl.Select(
          cnxn, cols=['project_name', 'project_id'], project_name=missed_names)
      retrieved_dict = dict(rows)
      self.project_names_to_ids.CacheAll(retrieved_dict)
      id_dict.update(retrieved_dict)

    return id_dict

  def LookupProjectNames(self, cnxn, project_ids):
    """Lookup the names of the projects with the given IDs."""
    projects_dict = self.GetProjects(cnxn, project_ids)
    return {p.project_id: p.project_name
            for p in projects_dict.itervalues()}

  ### Retrieving projects

  def GetAllProjects(self, cnxn, use_cache=True):
    """Return A dict mapping IDs to all live project PBs."""
    project_rows = self.project_tbl.Select(
        cnxn, cols=['project_id'], state=project_pb2.ProjectState.LIVE)
    project_ids = [row[0] for row in project_rows]
    projects_dict = self.GetProjects(cnxn, project_ids, use_cache=use_cache)

    return projects_dict

  def GetVisibleLiveProjects(self, cnxn, logged_in_user, effective_ids,
                             use_cache=True):
    """Return all user visible live project ids.

    Args:
      cnxn: connection to SQL database.
      logged_in_user: protocol buffer of the logged in user. Can be None.
      effective_ids: set of user IDs for this user. Can be None.
      use_cache: pass False to force database query to find Project protocol
                 buffers.

    Returns:
      A list of project ids of user visible live projects sorted by the names
      of the projects.
    """
    project_rows = self.project_tbl.Select(
        cnxn, cols=['project_id'], state=project_pb2.ProjectState.LIVE)
    project_ids = [row[0] for row in project_rows]
    projects_dict = self.GetProjects(cnxn, project_ids, use_cache=use_cache)

    visible_projects = [project for project in projects_dict.values()
                        if permissions.UserCanViewProject(
                            logged_in_user, effective_ids, project)]
    visible_projects.sort(key=lambda p: p.project_name)

    return [project.project_id for project in visible_projects]

  def GetProjects(self, cnxn, project_ids, use_cache=True):
    """Load all the Project PBs for the given projects.

    Args:
      cnxn: connection to SQL database.
      project_ids: list of int project IDs
      use_cache: pass False to force database query.

    Returns:
      A dict mapping IDs to the corresponding Project protocol buffers.

    Raises:
      NoSuchProjectException: if any of the projects was not found.
    """
    project_dict, missed_ids = self.project_2lc.GetAll(
        cnxn, project_ids, use_cache=use_cache)

    # Also, update the project name cache.
    self.project_names_to_ids.CacheAll(
        {p.project_name: p.project_id for p in project_dict.itervalues()})

    if missed_ids:
      raise NoSuchProjectException()

    return project_dict

  def GetProject(self, cnxn, project_id, use_cache=True):
    """Load the specified project from the database."""
    project_id_dict = self.GetProjects(cnxn, [project_id], use_cache=use_cache)
    return project_id_dict[project_id]

  def GetProjectsByName(self, cnxn, project_names, use_cache=True):
    """Load all the Project PBs for the given projects.

    Args:
      cnxn: connection to SQL database.
      project_names: list of project names.
      use_cache: specifify False to force database query.

    Returns:
      A dict mapping names to the corresponding Project protocol buffers.
    """
    project_ids = self.LookupProjectIDs(cnxn, project_names).values()
    projects = self.GetProjects(cnxn, project_ids, use_cache=use_cache)
    return {p.project_name: p for p in projects.itervalues()}

  def GetProjectByName(self, cnxn, project_name, use_cache=True):
    """Load the specified project from the database, None if does not exist."""
    project_dict = self.GetProjectsByName(
        cnxn, [project_name], use_cache=use_cache)
    return project_dict.get(project_name)

  ### Deleting projects

  def ExpungeProject(self, cnxn, project_id):
    """Wipes a project from the system."""
    logging.info('expunging project %r', project_id)
    self.user2project_tbl.Delete(cnxn, project_id=project_id)
    self.usergroupprojects_tbl.Delete(cnxn, project_id=project_id)
    self.extraperm_tbl.Delete(cnxn, project_id=project_id)
    self.membernotes_tbl.Delete(cnxn, project_id=project_id)
    self.acexclusion_tbl.Delete(cnxn, project_id=project_id)
    self.project_tbl.Delete(cnxn, project_id=project_id)

  ### Updating projects

  def UpdateProject(
      self, cnxn, project_id, summary=None, description=None,
      state=None, state_reason=None, access=None, issue_notify_address=None,
      attachment_bytes_used=None, attachment_quota=None, moved_to=None,
      process_inbound_email=None, only_owners_remove_restrictions=None,
      read_only_reason=None, cached_content_timestamp=None,
      only_owners_see_contributors=None, delete_time=None,
      recent_activity=None, revision_url_format=None, home_page=None,
      docs_url=None, source_url=None, logo_gcs_id=None, logo_file_name=None):
    """Update the DB with the given project information."""
    exists = self.project_tbl.SelectValue(
      cnxn, 'project_name', project_id=project_id)
    if not exists:
      raise NoSuchProjectException()

    delta = {}
    if summary is not None:
      delta['summary'] = summary
    if description is not None:
      delta['description'] = description
    if state is not None:
      delta['state'] = str(state).lower()
    if state is not None:
      delta['state_reason'] = state_reason
    if access is not None:
      delta['access'] = str(access).lower()
    if read_only_reason is not None:
      delta['read_only_reason'] = read_only_reason
    if issue_notify_address is not None:
      delta['issue_notify_address'] = issue_notify_address
    if attachment_bytes_used is not None:
      delta['attachment_bytes_used'] = attachment_bytes_used
    if attachment_quota is not None:
      delta['attachment_quota'] = attachment_quota
    if moved_to is not None:
      delta['moved_to'] = moved_to
    if process_inbound_email is not None:
      delta['process_inbound_email'] = process_inbound_email
    if only_owners_remove_restrictions is not None:
      delta['only_owners_remove_restrictions'] = (
          only_owners_remove_restrictions)
    if only_owners_see_contributors is not None:
      delta['only_owners_see_contributors'] = only_owners_see_contributors
    if delete_time is not None:
      delta['delete_time'] = delete_time
    if recent_activity is not None:
      delta['recent_activity_timestamp'] = recent_activity
    if revision_url_format is not None:
      delta['revision_url_format'] = revision_url_format
    if home_page is not None:
      delta['home_page'] = home_page
    if docs_url is not None:
      delta['docs_url'] = docs_url
    if source_url is not None:
      delta['source_url'] = source_url
    if logo_gcs_id is not None:
      delta['logo_gcs_id'] = logo_gcs_id
    if logo_file_name is not None:
      delta['logo_file_name'] = logo_file_name
    if cached_content_timestamp is not None:
      delta['cached_content_timestamp'] = cached_content_timestamp
    self.project_tbl.Update(cnxn, delta, project_id=project_id)
    self.project_2lc.InvalidateKeys(cnxn, [project_id])

  def UpdateProjectRoles(
      self, cnxn, project_id, owner_ids, committer_ids, contributor_ids,
      now=None):
    """Store the project's roles in the DB and set cached_content_timestamp."""
    exists = self.project_tbl.SelectValue(
      cnxn, 'project_name', project_id=project_id)
    if not exists:
      raise NoSuchProjectException()

    now = now or int(time.time())
    self.project_tbl.Update(
        cnxn, {'cached_content_timestamp': now},
        project_id=project_id)

    self.user2project_tbl.Delete(
        cnxn, project_id=project_id, role_name='owner', commit=False)
    self.user2project_tbl.Delete(
        cnxn, project_id=project_id, role_name='committer', commit=False)
    self.user2project_tbl.Delete(
        cnxn, project_id=project_id, role_name='contributor', commit=False)

    self.user2project_tbl.InsertRows(
        cnxn, ['project_id', 'user_id', 'role_name'],
        [(project_id, user_id, 'owner') for user_id in owner_ids],
        commit=False)
    self.user2project_tbl.InsertRows(
        cnxn, ['project_id', 'user_id', 'role_name'],
        [(project_id, user_id, 'committer')
         for user_id in committer_ids], commit=False)

    self.user2project_tbl.InsertRows(
        cnxn, ['project_id', 'user_id', 'role_name'],
        [(project_id, user_id, 'contributor')
         for user_id in contributor_ids], commit=False)

    cnxn.Commit()
    self.project_2lc.InvalidateKeys(cnxn, [project_id])

  def MarkProjectDeletable(self, cnxn, project_id, config_service):
    """Update the project's state to make it DELETABLE and free up the name.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project that will be deleted soon.
      config_service: issue tracker configuration persistence service, needed
          to invalidate cached issue tracker results.
    """
    generated_name = 'DELETABLE_%d' % project_id
    delta = {'project_name': generated_name, 'state': 'deletable'}
    self.project_tbl.Update(cnxn, delta, project_id=project_id)

    self.project_2lc.InvalidateKeys(cnxn, [project_id])
    # We cannot invalidate a specific part of the name->proj cache by name,
    # So, tell every job to just drop the whole cache.  It should refill
    # efficiently and incrementally from memcache.
    self.project_2lc.InvalidateAllRamEntries(cnxn)
    config_service.InvalidateMemcacheForEntireProject(project_id)

  def UpdateRecentActivity(self, cnxn, project_id, now=None):
    """Set the project's recent_activity to the current time."""
    now = now or int(time.time())
    self.UpdateProject(cnxn, project_id, recent_activity=now)

  ### Roles and extra perms

  def GetUserRolesInAllProjects(self, cnxn, effective_ids):
    """Return three sets of project IDs where the user has a role."""
    owned_project_ids = set()
    membered_project_ids = set()
    contrib_project_ids = set()

    rows = self.user2project_tbl.Select(
        cnxn, cols=['project_id', 'role_name'], user_id=effective_ids)

    for project_id, role_name in rows:
      if role_name == 'owner':
        owned_project_ids.add(project_id)
      elif role_name == 'committer':
        membered_project_ids.add(project_id)
      elif role_name == 'contributor':
        contrib_project_ids.add(project_id)
      else:
        logging.warn('Unexpected role name %r', role_name)

    return owned_project_ids, membered_project_ids, contrib_project_ids

  def UpdateExtraPerms(
      self, cnxn, project_id, member_id, extra_perms, now=None):
    """Load the project, update the member's extra perms, and store.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      member_id: int user id of the user that was edited.
      extra_perms: list of strings for perms that the member
          should have over-and-above what their role gives them.
      now: fake int(time.time()) value passed in during unit testing.
    """
    # This will be a newly constructed object, not from the cache and not
    # shared with any other thread.
    project = self.GetProject(cnxn, project_id, use_cache=False)

    member_extra_perms = permissions.FindExtraPerms(project, member_id)
    if not member_extra_perms and not extra_perms:
      return
    if member_extra_perms and list(member_extra_perms.perms) == extra_perms:
      return

    if member_extra_perms:
      member_extra_perms.perms = extra_perms
    else:
      member_extra_perms = project_pb2.Project.ExtraPerms(
          member_id=member_id, perms=extra_perms)
      project.extra_perms.append(member_extra_perms)

    self.extraperm_tbl.Delete(
        cnxn, project_id=project_id, user_id=member_id, commit=False)
    self.extraperm_tbl.InsertRows(
        cnxn, EXTRAPERM_COLS,
        [(project_id, member_id, perm) for perm in extra_perms],
        commit=False)
    now = now or int(time.time())
    project.cached_content_timestamp = now
    self.project_tbl.Update(
        cnxn, {'cached_content_timestamp': project.cached_content_timestamp},
        project_id=project_id, commit=False)
    cnxn.Commit()

    self.project_2lc.InvalidateKeys(cnxn, [project_id])

  ### Project Commitments

  def GetProjectCommitments(self, cnxn, project_id):
    """Get the project commitments (notes) from the DB.

    Args:
      cnxn: connection to SQL database.
      project_id: int project ID.

    Returns:
      A the specified project's ProjectCommitments instance, or an empty one,
        if the project doesn't exist, or has not documented member
        commitments.
    """
    # Get the notes.  Don't get the project_id column
    # since we already know that value.
    notes_rows = self.membernotes_tbl.Select(
        cnxn, cols=['user_id', 'notes'], project_id=project_id)
    notes_dict = dict(notes_rows)

    project_commitments = project_pb2.ProjectCommitments()
    project_commitments.project_id = project_id
    for user_id in notes_dict.keys():
      commitment = project_pb2.ProjectCommitments.MemberCommitment(
          member_id=user_id,
          notes=notes_dict.get(user_id, ''))
      project_commitments.commitments.append(commitment)

    return project_commitments

  def _StoreProjectCommitments(self, cnxn, project_commitments):
    """Store an updated set of project commitments in the DB.

    Args:
      cnxn: connection to SQL database.
      project_commitments: ProjectCommitments PB
    """
    project_id = project_commitments.project_id
    notes_rows = []
    for commitment in project_commitments.commitments:
      notes_rows.append(
          (project_id, commitment.member_id, commitment.notes))

    # TODO(jrobbins): this should be in a transaction.
    self.membernotes_tbl.Delete(cnxn, project_id=project_id)
    self.membernotes_tbl.InsertRows(
        cnxn, MEMBERNOTES_COLS, notes_rows, ignore=True)

  def UpdateCommitments(self, cnxn, project_id, member_id, notes):
    """Update the member's commitments in the specified project.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      member_id: int user ID of the user that was edited.
      notes: further notes on the member's expected involvment
        in the project.
    """
    project_commitments = self.GetProjectCommitments(cnxn, project_id)

    commitment = None
    for c in project_commitments.commitments:
      if c.member_id == member_id:
        commitment = c
        break
    else:
      commitment = project_pb2.ProjectCommitments.MemberCommitment(
          member_id=member_id)
      project_commitments.commitments.append(commitment)

    dirty = False

    if commitment.notes != notes:
      commitment.notes = notes
      dirty = True

    if dirty:
      self._StoreProjectCommitments(cnxn, project_commitments)

  def GetProjectAutocompleteExclusion(self, cnxn, project_id):
    """Get user ids who are excluded from autocomplete list.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.

    Returns:
      A list of user ids who are excluded from autocomplete list for given
      project.
    """
    acexclusion_rows = self.acexclusion_tbl.Select(
        cnxn, cols=['user_id'], project_id=project_id)
    user_ids = [row[0] for row in acexclusion_rows]
    return user_ids

  def UpdateProjectAutocompleteExclusion(
      self, cnxn, project_id, member_id, exclude):
    """Update autocomplete exclusion for given user.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      member_id: int user ID of the user that was edited.
      exclude: Whether this user should be excluded.
    """
    if exclude:
      self.acexclusion_tbl.InsertRows(
        cnxn, AUTOCOMPLETEEXCLUSION_COLS, [(project_id, member_id)],
        ignore=True)
    else:
      self.acexclusion_tbl.Delete(
          cnxn, project_id=project_id, user_id=member_id)


class Error(Exception):
  """Base exception class for this package."""


class ProjectAlreadyExists(Error):
  """Tried to create a project that already exists."""


class NoSuchProjectException(Error):
  """No project with the specified name exists."""
  pass
