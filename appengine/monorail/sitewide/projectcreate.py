# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes for users to create a new project."""


import logging
from third_party import ezt

import settings
from businesslogic import work_env
from framework import actionlimit
from framework import exceptions
from framework import filecontent
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import gcs_helpers
from framework import jsonfeed
from framework import permissions
from framework import servlet
from framework import urls
from project import project_helpers
from project import project_views
from services import project_svc
from tracker import tracker_bizobj
from tracker import tracker_views


_MSG_PROJECT_NAME_NOT_AVAIL = 'That project name is not available.'
_MSG_MISSING_PROJECT_NAME = 'Missing project name'
_MSG_INVALID_PROJECT_NAME = 'Invalid project name'
_MSG_MISSING_PROJECT_SUMMARY = 'Missing project summary'


class ProjectCreate(servlet.Servlet):
  """Shows a page with a simple form to create a project."""

  _PAGE_TEMPLATE = 'sitewide/project-create-page.ezt'

  _CAPTCHA_ACTION_TYPES = [actionlimit.PROJECT_CREATION]

  def AssertBasePermission(self, mr):
    """Assert that the user has the permissions needed to view this page."""
    super(ProjectCreate, self).AssertBasePermission(mr)

    if not permissions.CanCreateProject(mr.perms):
      raise permissions.PermissionException(
          'User is not allowed to create a project')

  def GatherPageData(self, _mr):
    """Build up a dictionary of data values to use when rendering the page."""
    available_access_levels = project_helpers.BuildProjectAccessOptions(None)
    offer_access_level = len(available_access_levels) > 1
    if settings.default_access_level:
      access_view = project_views.ProjectAccessView(
          settings.default_access_level)
    else:
      access_view = None

    return {
        'initial_name': '',
        'initial_summary': '',
        'initial_description': '',
        'initial_project_home': '',
        'initial_docs_url': '',
        'initial_source_url': '',
        'initial_logo_gcs_id': '',
        'initial_logo_file_name': '',
        'logo_view': tracker_views.LogoView(None),
        'labels': [],
        'max_project_name_length': framework_constants.MAX_PROJECT_NAME_LENGTH,
        'offer_access_level': ezt.boolean(offer_access_level),
        'initial_access': access_view,
        'available_access_levels': available_access_levels,
        }

  def GatherHelpData(self, mr, page_data):
    """Return a dict of values to drive on-page user help.

    Args:
      mr: common information parsed from the HTTP request.
      page_data: Dictionary of base and page template data.

    Returns:
      A dict of values to drive on-page user help, to be added to page_data.
    """
    help_data = super(ProjectCreate, self).GatherHelpData(mr, page_data)
    cue_remaining_projects = None

    (_period, _soft, _hard,
     life_max) = actionlimit.ACTION_LIMITS[actionlimit.PROJECT_CREATION]
    actionlimit_pb = actionlimit.GetLimitPB(
        mr.auth.user_pb, actionlimit.PROJECT_CREATION)
    if actionlimit_pb.get_assigned_value('lifetime_limit'):
      life_max = actionlimit_pb.lifetime_limit
    if life_max is not None:
      if (actionlimit_pb.lifetime_count + 10 >= life_max
          and actionlimit_pb.lifetime_count < life_max):
        cue_remaining_projects = life_max - actionlimit_pb.lifetime_count

    help_data.update({
        'cue_remaining_projects': cue_remaining_projects,
        })
    return help_data

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    # 1. Parse and validate user input.
    # Project name is taken from post_data because we are creating it.
    project_name = post_data.get('projectname')
    if not project_name:
      mr.errors.projectname = _MSG_MISSING_PROJECT_NAME
    elif not framework_bizobj.IsValidProjectName(project_name):
      mr.errors.projectname = _MSG_INVALID_PROJECT_NAME

    summary = post_data.get('summary')
    if not summary:
      mr.errors.summary = _MSG_MISSING_PROJECT_SUMMARY
    description = post_data.get('description', '')

    access = project_helpers.ParseProjectAccess(None, post_data.get('access'))
    home_page = post_data.get('project_home')
    if home_page and not (
        home_page.startswith('http://') or home_page.startswith('https://')):
      mr.errors.project_home = 'Home page link must start with http(s)://'
    docs_url = post_data.get('docs_url')
    if docs_url and not (
        docs_url.startswith('http:') or docs_url.startswith('https:')):
      mr.errors.docs_url = 'Documentation link must start with http: or https:'

    self.CheckCaptcha(mr, post_data)

    # These are not specified on via the ProjectCreate form,
    # the user must edit the project after creation to set them.
    committer_ids = []
    contributor_ids = []

    # Validate that provided logo is supported.
    logo_provided = 'logo' in post_data and not isinstance(
        post_data['logo'], basestring)
    if logo_provided:
      item = post_data['logo']
      try:
        gcs_helpers.CheckMimeTypeResizable(
            filecontent.GuessContentTypeFromFilename(item.filename))
      except gcs_helpers.UnsupportedMimeType, e:
        mr.errors.logo = e.message

    # 2. Call services layer to save changes.
    if not mr.errors.AnyErrors():
      with work_env.WorkEnv(mr, self.services) as we:
        try:
          project_id = we.CreateProject(
              project_name, [mr.auth.user_id],
              committer_ids, contributor_ids, summary, description,
              access=access, home_page=home_page, docs_url=docs_url)

          config = tracker_bizobj.MakeDefaultProjectIssueConfig(project_id)
          self.services.config.StoreConfig(mr.cnxn, config)
          # Note: No need to store any canned queries or rules yet.
          self.services.issue.InitializeLocalID(mr.cnxn, project_id)

          # Update project with  logo if specified.
          if logo_provided:
            item = post_data['logo']
            logo_file_name = item.filename
            logo_gcs_id = gcs_helpers.StoreLogoInGCS(
                logo_file_name, item.value, project_id)
            we.UpdateProject(
                project_id, logo_gcs_id=logo_gcs_id,
                logo_file_name=logo_file_name)

          self.CountRateLimitedActions(
              mr, {actionlimit.PROJECT_CREATION: 1})
        except exceptions.ProjectAlreadyExists:
          mr.errors.projectname = _MSG_PROJECT_NAME_NOT_AVAIL

    # 3. Determine the next page in the UI flow.
    if mr.errors.AnyErrors():
      access_view = project_views.ProjectAccessView(access)
      self.PleaseCorrect(
          mr, initial_summary=summary, initial_description=description,
          initial_name=project_name, initial_access=access_view)
    else:
      # Go to the new project's introduction page.
      return framework_helpers.FormatAbsoluteURL(
          mr, urls.ADMIN_INTRO, project_name=project_name)


class CheckProjectNameJSON(jsonfeed.JsonFeed):
  """JSON data for handling project name checks when creating a project."""

  def HandleRequest(self, mr):
    """Provide the UI with info about the availability of the project name.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format.
    """
    if self.services.project.LookupProjectIDs(mr.cnxn, [mr.specified_project]):
      return {'error_message': _MSG_PROJECT_NAME_NOT_AVAIL}

    return {'error_message': ''}
