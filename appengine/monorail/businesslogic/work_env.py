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
+ API: check oauth client whitelist
+ Create a MonorailRequest object:
  - Parse the request, including syntaxtic validation, e.g, non-negative ints
  - Authenticate the requesting user
+ Call the WorkEnvironment to perform the requested action
  - Catch exceptions and generate error messages
+ UI: Decide screen flow, and on-page online-help
+ Render the result business objects as UI HTML or API response protobufs.

Responsibilities of WorkEnv:
+ Rate-limiting and spam-fighting
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

from framework import exceptions
from services import project_svc

# TODO(jrobbins): rate limiting and permission checking in each method.

# TODO(jrobbins): break this file into one facade plus ~5
# implementation parts that roughly correspond to services files.


class WorkEnv(object):

  def __init__(self, mr, services, phase=None):
    self.mr = mr
    self.services = services
    self.phase = phase

  def __enter__(self):
    if self.mr.profiler and self.phase:
      self.mr.profiler.StartPhase(name=self.phase)
    return self  # The instance of this class is the context object.

  def __exit__(self, exception_type, value, traceback):
    if self.mr.profiler and self.phase:
      self.mr.profiler.EndPhase()
    return False  # Re-raise any exception in the with-block.

  ### Site methods

  # FUTURE: GetSiteReadOnlyState()
  # FUTURE: SetSiteReadOnlyState()
  # FUTURE: GetSiteBannerMessage()
  # FUTURE: SetSiteBannerMessage()

  ### Project methods

  # FUTURE: CreateProject()
  # FUTURE: ListProjects()

  def GetProject(self, project_id, use_cache=True):
    """Return the specified project, TODO: iff the signed in user may view it.

    Args:
      project_id: int project_id of the project to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified project.

    Raise:
      project_svc.NoSuchProjectException if there is no project with that ID.
    """
    with self.mr.profiler.Phase('getting project %r' % project_id):
      project = self.services.project.GetProject(
          self.mr.cnxn, project_id, use_cache=use_cache)
    return project

  def GetProjectByName(self, project_name, use_cache=True):
    """Return the named project, TODO: iff the signed in user may view it.

    Args:
      project_name: string name of the project to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified project.

    Raise:
      project_svc.NoSuchProjectException if there is no project with that name.
    """
    with self.mr.profiler.Phase('getting project %r' % project_name):
      project = self.services.project.GetProjectByName(
          self.mr.cnxn, project_name, use_cache=use_cache)
    if not project:
      raise project_svc.NoSuchProjectException()
    return project

  # FUTURE: UpdateProject()
  # FUTURE: DeleteProject()

  # FUTURE: SetProjectStar()
  # FUTURE: GetProjectStarsByUser()

  def GetProjectConfig(self, project_id, use_cache=True):
    """Return the specifed config, TODO: iff the signed in user may view it.

    Args:
      project_name: string name of the project to retrieve.
      use_cache: set to false when doing read-modify-write.

    Returns:
      The specified config.

    Raise:
      project_svc.NoSuchProjectException if there is no matching config.
    """
    with self.mr.profiler.Phase('getting config for %r' % project_id):
      config = self.services.config.GetProjectConfig(
          self.mr.cnxn, project_id, use_cache=use_cache)
    if not config:
      raise project_svc.NoSuchProjectException()
    return config

  # FUTURE: labels, statuses, fields, components, rules, templates, and views.
  # FUTURE: project saved queries.
  # FUTURE: GetProjectPermissionsForUser()

  ### Issue methods

  # FUTURE: CreateIssue()
  # FUTURE: ListIssues()

  def GetIssue(self, issue_id, use_cache=True):
    """Return the specified issue, TODO: iff the signed in user may view it."""
    with self.mr.profiler.Phase('getting issue %r' % issue_id):
      issue = self.services.issue.GetIssue(
          self.mr.cnxn, issue_id, use_cache=use_cache)
    return issue

  def GetIssueByLocalID(self, project_id, local_id, use_cache=True):
    """Return the specified issue, TODO: iff the signed in user may view it.

    Args:
      project_id: int project ID of the project that contains the issue.
      local_id: int issue local id number.
      use_cache: set to False when doing read-modify-write operations.

    Returns:
      The specified Issue PB.

    Raises:
      exception.InputException if something was not specified properly.
      issue_svc.NoSuchIssueException if the issue does not exist.
    """
    if project_id is None:
      raise exceptions.InputException('No project specified')
    if local_id is None:
      raise exceptions.InputException('No issue local_id specified')

    with self.mr.profiler.Phase('getting issue %r:%r' % (project_id, local_id)):
      issue = self.services.issue.GetIssueByLocalID(
          self.mr.cnxn, project_id, local_id, use_cache=use_cache)
    return issue

  # FUTURE: UpdateIssue()
  # FUTURE: DeleteIssue()
  # FUTURE: GetIssuePermissionsForUser()

  # FUTURE: CreateComment()

  def ListIssueComments(self, viewable_issue):
    """Return comments on the specified viewable issue."""
    with self.mr.profiler.Phase(
        'getting comments for %r' % viewable_issue.issue_id):
      comments = self.services.issue.GetCommentsForIssue(
          self.mr.cnxn, viewable_issue.issue_id)
    return comments

  # FUTURE: UpdateComment()
  # FUTURE: DeleteComment()

  # FUTURE: SetIssueStar()
  # FUTURE: GetIssueStars()
  # FUTURE: GetIssueStarsByUser()

  ### User methods

  # FUTURE: GetUser()
  # FUTURE: UpdateUser()
  # FUTURE: DeleteUser()

  ### Group methods

  # FUTURE: CreateGroup()
  # FUTURE: ListGroups()
  # FUTURE: UpdateGroup()
  # FUTURE: DeleteGroup()

  ### Hotlist methods

  # FUTURE: CreateHotlist()
  # FUTURE: ListHotlistsByUser()
  # FUTURE: UpdateHotlist()
  # FUTURE: DeleteHotlist()
