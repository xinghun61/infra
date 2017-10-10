# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Page and form handlers for project administration "advanced" subtab.

The advanced subtab allows the project to be archived, unarchived, deleted, or
marked as moved.  Site admins can use this page to "doom" a project, which is
basically archiving it in a way that cannot be reversed by the project owners.

The page also shows project data storage quota and usage values, and
site admins can edit those quotas.
"""

import logging
import time

from third_party import ezt

from businesslogic import work_env
from framework import framework_constants
from framework import framework_helpers
from framework import permissions
from framework import servlet
from framework import template_helpers
from framework import urls
from proto import project_pb2
from tracker import tracker_constants


class ProjectAdminAdvanced(servlet.Servlet):
  """A page with project state options for the Project Owner(s)."""

  _PAGE_TEMPLATE = 'project/project-admin-advanced-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ADMIN

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(ProjectAdminAdvanced, self).AssertBasePermission(mr)
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'User is not allowed to administer this project')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the "Advanced" subtab.
    """
    page_data = {
        'admin_tab_mode': self.ADMIN_TAB_ADVANCED,
        }
    page_data.update(self._GatherPublishingOptions(mr))
    page_data.update(self._GatherQuotaData(mr))

    return page_data

  def _GatherPublishingOptions(self, mr):
    """Gather booleans to control the publishing buttons to show in EZT."""
    state = mr.project.state
    offer_archive = state != project_pb2.ProjectState.ARCHIVED
    offer_delete = state == project_pb2.ProjectState.ARCHIVED
    offer_publish = (
        state == project_pb2.ProjectState.ARCHIVED and
        (self.CheckPerm(mr, permissions.PUBLISH_PROJECT) or
         not mr.project.state_reason))
    offer_move = state == project_pb2.ProjectState.LIVE
    offer_doom = self.CheckPerm(mr, permissions.ADMINISTER_SITE)
    moved_to = mr.project.moved_to or 'http://'

    publishing_data = {
        'offer_archive': ezt.boolean(offer_archive),
        'offer_publish': ezt.boolean(offer_publish),
        'offer_delete': ezt.boolean(offer_delete),
        'offer_move': ezt.boolean(offer_move),
        'moved_to': moved_to,
        'offer_doom': ezt.boolean(offer_doom),
        'default_doom_reason': framework_constants.DEFAULT_DOOM_REASON,
        }

    return publishing_data

  def _GatherQuotaData(self, mr):
    """Gather quota info from backends so that it can be passed to EZT."""
    offer_quota_editing = self.CheckPerm(mr, permissions.EDIT_QUOTA)

    quota_data = {
        'offer_quota_editing': ezt.boolean(offer_quota_editing),
        'attachment_quota': self._BuildAttachmentQuotaData(mr.project),
        }

    return quota_data

  def _BuildComponentQuota(self, used_bytes, quota_bytes, field_name):
    """Return an object to easily display quota info in EZT."""
    if quota_bytes:
      used_percent = 100 * used_bytes / quota_bytes
    else:
      used_percent = 0

    quota_mb = quota_bytes / 1024 / 1024

    return template_helpers.EZTItem(
        used=template_helpers.BytesKbOrMb(used_bytes),
        quota_mb=quota_mb,
        used_percent=used_percent,
        avail_percent=100 - used_percent,
        field_name=field_name)

  def _BuildAttachmentQuotaData(self, project):
    return self._BuildComponentQuota(
      project.attachment_bytes_used,
      project.attachment_quota or
      tracker_constants.ISSUE_ATTACHMENTS_QUOTA_HARD,
      'attachment_quota_mb')

  def ProcessFormData(self, mr, post_data):
    """Process the posted form.

    Args:
      mr: commonly used info parsed from the request.
      post_data: dictionary of HTML form data.

    Returns:
      String URL to redirect to after processing is completed.
    """
    if 'savechanges' in post_data:
      self._ProcessQuota(mr, post_data)
    else:
      self._ProcessPublishingOptions(mr, post_data)

    if 'deletebtn' in post_data:
      url = framework_helpers.FormatAbsoluteURL(
          mr, urls.HOSTING_HOME, include_project=False)
    else:
      url = framework_helpers.FormatAbsoluteURL(
          mr, urls.ADMIN_ADVANCED, saved=1, ts=int(time.time()))

    return url

  def _ProcessQuota(self, mr, post_data):
    """Process form data to update project quotas."""
    if not self.CheckPerm(mr, permissions.EDIT_QUOTA):
      raise permissions.PermissionException(
          'User is not allowed to change project quotas')

    try:
      new_attachment_quota = int(post_data['attachment_quota_mb'])
      new_attachment_quota *= 1024 * 1024
    except ValueError:
      mr.errors.attachment_quota = 'Invalid value'
      self.PleaseCorrect(mr)  # Don't echo back the bad input, just start over.
      return

    with work_env.WorkEnv(mr, self.services) as we:
      we.UpdateProject(
          mr.project.project_id, attachment_quota=new_attachment_quota)

  def _ProcessPublishingOptions(self, mr, post_data):
    """Process form data to update project state."""
    # Note that EDIT_PROJECT is the base permission for this servlet, but
    # dooming and undooming projects also requires PUBLISH_PROJECT.

    state = mr.project.state

    with work_env.WorkEnv(mr, self.services) as we:
      if 'archivebtn' in post_data and not mr.project.delete_time:
        we.UpdateProject(
            mr.project.project_id, state=project_pb2.ProjectState.ARCHIVED)

      elif 'deletebtn' in post_data:  # Mark the project for immediate deletion.
        if state != project_pb2.ProjectState.ARCHIVED:
          raise permissions.PermissionException(
              'Projects must be archived before being deleted')
        self.services.project.MarkProjectDeletable(
            mr.cnxn, mr.project_id, self.services.config)

      elif 'doombtn' in post_data:  # Go from any state to forced ARCHIVED.
        if not self.CheckPerm(mr, permissions.PUBLISH_PROJECT):
          raise permissions.PermissionException(
              'User is not allowed to doom projects')
        reason = post_data.get('reason')
        delete_time = time.time() + framework_constants.DEFAULT_DOOM_PERIOD
        we.UpdateProject(
            mr.project.project_id, state=project_pb2.ProjectState.ARCHIVED,
            state_reason=reason, delete_time=delete_time)

      elif 'publishbtn' in post_data:  # Go from any state to LIVE
        if (mr.project.delete_time and
            not self.CheckPerm(mr, permissions.PUBLISH_PROJECT)):
          raise permissions.PermissionException(
              'User is not allowed to unarchive doomed projects')
        we.UpdateProject(
            mr.project.project_id, state=project_pb2.ProjectState.LIVE,
            state_reason='', delete_time=0, read_only_reason='')

      elif 'movedbtn' in post_data:  # Record the moved_to location.
        if state != project_pb2.ProjectState.LIVE:
          raise permissions.PermissionException(
              'This project is not live, no user can move it')
        moved_to = post_data.get('moved_to', '')
        we.UpdateProject(mr.project.project_id, moved_to=moved_to)
