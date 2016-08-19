# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes for the user profile page ("my page")."""

import logging
import time

from third_party import ezt

from framework import framework_helpers
from framework import framework_views
from framework import permissions
from framework import servlet
from project import project_views
from sitewide import sitewide_helpers


class AbstractUserPage(servlet.Servlet):
  """Base class for UserProfile and UserUpdates pages."""

  _PAGE_TEMPLATE = None

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    raise NotImplementedError()


class UserProfile(AbstractUserPage):
  """Shows a page of information about a user."""

  _PAGE_TEMPLATE = 'sitewide/user-profile-page.ezt'

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    if self.services.usergroup.GetGroupSettings(
        mr.cnxn, mr.viewed_user_auth.user_id):
      url = framework_helpers.FormatAbsoluteURL(
          mr, '/g/%s/' % mr.viewed_user_auth.user_pb.email,
          include_project=False)
      self.redirect(url, abort=True)  # Show group page instead.

    with self.profiler.Phase('GetUserProjects'):
      project_lists = sitewide_helpers.GetUserProjects(
          mr.cnxn, self.services, mr.auth.user_pb, mr.auth.effective_ids,
          mr.viewed_user_auth.effective_ids)

      (visible_ownership, visible_archived, visible_membership,
       visible_contrib) = project_lists

    viewed_user_display_name = framework_views.GetViewedUserDisplayName(mr)

    with self.profiler.Phase('GetStarredProjects'):
      starred_projects = sitewide_helpers.GetViewableStarredProjects(
          mr.cnxn, self.services, mr.viewed_user_auth.user_id,
          mr.auth.effective_ids, mr.auth.user_pb)

    logged_in_starred_pids = []
    if mr.auth.user_id:
      logged_in_starred_pids = self.services.project_star.LookupStarredItemIDs(
          mr.cnxn, mr.auth.user_id)

    starred_user_ids = self.services.user_star.LookupStarredItemIDs(
        mr.cnxn, mr.viewed_user_auth.user_id)
    starred_user_dict = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user, starred_user_ids)
    starred_users = starred_user_dict.values()

    is_user_starred = self._IsUserStarred(
        mr.cnxn, mr.auth.user_id, mr.viewed_user_auth.user_id)

    page_data = {
        'user_tab_mode': 'st2',
        'viewed_user_display_name': viewed_user_display_name,
        'viewed_user_is_banned': ezt.boolean(
            mr.viewed_user_auth.user_pb.banned),
        'viewed_user_ignore_action_limits': (
            ezt.boolean(mr.viewed_user_auth.user_pb.ignore_action_limits)),
        'owner_of_projects': [
            project_views.ProjectView(
                p, starred=p.project_id in logged_in_starred_pids)
            for p in visible_ownership],
        'committer_of_projects': [
            project_views.ProjectView(
                p, starred=p.project_id in logged_in_starred_pids)
            for p in visible_membership],
        'contributor_to_projects': [
            project_views.ProjectView(
                p, starred=p.project_id in logged_in_starred_pids)
            for p in visible_contrib],
        'owner_of_archived_projects': [
            project_views.ProjectView(p) for p in visible_archived],
        'starred_projects': [
            project_views.ProjectView(
                p, starred=p.project_id in logged_in_starred_pids)
            for p in starred_projects],
        'starred_users': starred_users,
        'is_user_starred': ezt.boolean(is_user_starred),
        'viewing_user_page': ezt.boolean(True),
        }

    settings = framework_helpers.UserSettings.GatherUnifiedSettingsPageData(
        mr.auth.user_id, mr.viewed_user_auth.user_view,
        mr.viewed_user_auth.user_pb)
    page_data.update(settings)

    return page_data

  def _IsUserStarred(self, cnxn, logged_in_user_id, viewed_user_id):
    """Return whether the logged in user starred the viewed user."""
    if logged_in_user_id:
      return self.services.user_star.IsItemStarredBy(
          cnxn, viewed_user_id, logged_in_user_id)
    return False

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    has_admin_perm = mr.perms.HasPerm(permissions.ADMINISTER_SITE, None, None)
    framework_helpers.UserSettings.ProcessSettingsForm(
        mr.cnxn, self.services.user, post_data, mr.viewed_user_auth.user_id,
        mr.viewed_user_auth.user_pb, admin=has_admin_perm)

    # TODO(jrobbins): Check all calls to FormatAbsoluteURL for include_project.
    return framework_helpers.FormatAbsoluteURL(
        mr, mr.viewed_user_auth.user_view.profile_url, include_project=False,
        saved=1, ts=int(time.time()))
