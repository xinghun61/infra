# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlets for project administration main subtab."""

import logging
import time

from third_party import cloudstorage
from third_party import ezt

from businesslogic import work_env
from framework import emailfmt
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import gcs_helpers
from framework import permissions
from framework import servlet
from framework import urls
from framework import validate
from project import project_helpers
from project import project_views
from tracker import tracker_views


_MSG_INVALID_EMAIL_ADDRESS = 'Invalid email address'
_MSG_DESCRIPTION_MISSING = 'Description is missing'
_MSG_SUMMARY_MISSING = 'Summary is missing'


class ProjectAdmin(servlet.Servlet):
  """A page with project configuration options for the Project Owner(s)."""

  _PAGE_TEMPLATE = 'project/project-admin-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ADMIN

  def AssertBasePermission(self, mr):
    super(ProjectAdmin, self).AssertBasePermission(mr)
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'User is not allowed to administer this project')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    available_access_levels = project_helpers.BuildProjectAccessOptions(
        mr.project)
    offer_access_level = len(available_access_levels) > 1
    access_view = project_views.ProjectAccessView(mr.project.access)

    return {
        'admin_tab_mode': self.ADMIN_TAB_META,
        'initial_summary': mr.project.summary,
        'initial_project_home': mr.project.home_page,
        'initial_docs_url': mr.project.docs_url,
        'initial_source_url': mr.project.source_url,
        'initial_logo_gcs_id': mr.project.logo_gcs_id,
        'initial_logo_file_name': mr.project.logo_file_name,
        'logo_view': tracker_views.LogoView(mr.project),
        'initial_description': mr.project.description,
        'issue_notify': mr.project.issue_notify_address,
        'process_inbound_email': ezt.boolean(
            mr.project.process_inbound_email),
        'email_from_addr': emailfmt.FormatFromAddr(mr.project),
        'only_owners_remove_restrictions': ezt.boolean(
            mr.project.only_owners_remove_restrictions),
        'only_owners_see_contributors': ezt.boolean(
            mr.project.only_owners_see_contributors),
        'offer_access_level': ezt.boolean(offer_access_level),
        'initial_access': access_view,
        'available_access_levels': available_access_levels,
        }

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    # 1. Parse and validate user input.
    summary, description = self._ParseMeta(post_data, mr.errors)
    access = project_helpers.ParseProjectAccess(
        mr.project, post_data.get('access'))

    only_owners_remove_restrictions = (
        'only_owners_remove_restrictions' in post_data)
    only_owners_see_contributors = 'only_owners_see_contributors' in post_data

    issue_notify = post_data['issue_notify']
    if issue_notify and not validate.IsValidEmail(issue_notify):
      mr.errors.issue_notify = _MSG_INVALID_EMAIL_ADDRESS

    process_inbound_email = 'process_inbound_email' in post_data
    home_page = post_data.get('project_home')
    if home_page and not (
        home_page.startswith('http:') or home_page.startswith('https:')):
      mr.errors.project_home = 'Home page link must start with http: or https:'
    docs_url = post_data.get('docs_url')
    if docs_url and not (
        docs_url.startswith('http:') or docs_url.startswith('https:')):
      mr.errors.docs_url = 'Documentation link must start with http: or https:'
    source_url = post_data.get('source_url')
    if source_url and not (
        source_url.startswith('http:') or source_url.startswith('https:')):
      mr.errors.source_url = 'Source link must start with http: or https:'

    logo_gcs_id = ''
    logo_file_name = ''
    if 'logo' in post_data and not isinstance(post_data['logo'], basestring):
      item = post_data['logo']
      logo_file_name = item.filename
      try:
        logo_gcs_id = gcs_helpers.StoreLogoInGCS(
            logo_file_name, item.value, mr.project.project_id)
      except gcs_helpers.UnsupportedMimeType, e:
        mr.errors.logo = e.message
    elif mr.project.logo_gcs_id and mr.project.logo_file_name:
      logo_gcs_id = mr.project.logo_gcs_id
      logo_file_name = mr.project.logo_file_name
      if post_data.get('delete_logo'):
        try:
          gcs_helpers.DeleteObjectFromGCS(logo_gcs_id)
        except cloudstorage.NotFoundError:
          pass
        # Reset the GCS ID and file name.
        logo_gcs_id = ''
        logo_file_name = ''

    # 2. Call services layer to save changes.
    if not mr.errors.AnyErrors():
      with work_env.WorkEnv(mr, self.services) as we:
        we.UpdateProject(
            mr.project.project_id, issue_notify_address=issue_notify,
            summary=summary, description=description,
            only_owners_remove_restrictions=only_owners_remove_restrictions,
            only_owners_see_contributors=only_owners_see_contributors,
            process_inbound_email=process_inbound_email, access=access,
            home_page=home_page, docs_url=docs_url, source_url=source_url,
            logo_gcs_id=logo_gcs_id, logo_file_name=logo_file_name)

    # 3. Determine the next page in the UI flow.
    if mr.errors.AnyErrors():
      access_view = project_views.ProjectAccessView(access)
      self.PleaseCorrect(
          mr, initial_summary=summary, initial_description=description,
          initial_access=access_view)
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, urls.ADMIN_META, saved=1, ts=int(time.time()))

  def _ParseMeta(self, post_data, errors):
    """Process a POST on the project metadata section of the admin page."""
    summary = None
    description = None

    if 'summary' in post_data:
      summary = post_data['summary']
      if not summary:
        errors.summary = _MSG_SUMMARY_MISSING
    if 'description' in post_data:
      description = post_data['description']
      if not description:
        errors.description = _MSG_DESCRIPTION_MISSING

    return summary, description
