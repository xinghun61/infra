# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes for the user profile page ("my page")."""

import logging
import time

from third_party import ezt

from businesslogic import work_env
from framework import framework_helpers
from framework import framework_views
from framework import permissions
from framework import servlet
from framework import timestr
from framework import xsrf
from project import project_views
from sitewide import sitewide_helpers


class UserProfile(servlet.Servlet):
  """Shows a page of information about a user."""

  _PAGE_TEMPLATE = 'sitewide/user-profile-page.ezt'

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    viewed_user = mr.viewed_user_auth.user_pb
    if self.services.usergroup.GetGroupSettings(
        mr.cnxn, mr.viewed_user_auth.user_id):
      url = framework_helpers.FormatAbsoluteURL(
          mr, '/g/%s/' % viewed_user.email, include_project=False)
      self.redirect(url, abort=True)  # Show group page instead.

    with self.profiler.Phase('GetUserProjects'):
      project_lists = sitewide_helpers.GetUserProjects(
          mr.cnxn, self.services, mr.auth.user_pb, mr.auth.effective_ids,
          mr.viewed_user_auth.effective_ids)

      (visible_ownership, visible_archived, visible_membership,
       visible_contrib) = project_lists

    viewed_user_display_name = framework_views.GetViewedUserDisplayName(mr)

    with work_env.WorkEnv(mr, self.services) as we:
      starred_projects = we.ListStarredProjects(
          viewed_user_id=mr.viewed_user_auth.user_id)
      logged_in_starred = we.ListStarredProjects()
      logged_in_starred_pids = {p.project_id for p in logged_in_starred}

    starred_user_ids = self.services.user_star.LookupStarredItemIDs(
        mr.cnxn, mr.viewed_user_auth.user_id)
    starred_user_dict = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user, starred_user_ids)
    starred_users = starred_user_dict.values()

    is_user_starred = self._IsUserStarred(
        mr.cnxn, mr.auth.user_id, mr.viewed_user_auth.user_id)

    if viewed_user.last_visit_timestamp:
      last_visit_str = timestr.FormatRelativeDate(
          viewed_user.last_visit_timestamp, days_only=True)
      last_visit_str = last_visit_str or 'Less than 2 days ago'
    else:
      last_visit_str = 'Never'

    if viewed_user.email_bounce_timestamp:
      last_bounce_str = timestr.FormatRelativeDate(
          viewed_user.email_bounce_timestamp, days_only=True)
      last_bounce_str = last_bounce_str or 'Less than 2 days ago'
    else:
      last_bounce_str = None

    can_ban = permissions.CanBan(mr, self.services)
    viewed_user_is_spammer = viewed_user.banned.lower() == 'spam'
    viewed_user_may_be_spammer = not viewed_user_is_spammer
    all_projects = self.services.project.GetAllProjects(mr.cnxn)
    for project_id in all_projects:
      project = all_projects[project_id]
      viewed_user_perms = permissions.GetPermissions(viewed_user,
          mr.viewed_user_auth.effective_ids, project)
      if (viewed_user_perms != permissions.EMPTY_PERMISSIONSET and
          viewed_user_perms != permissions.USER_PERMISSIONSET):
        viewed_user_may_be_spammer = False

    ban_token = None
    ban_spammer_token = None
    if mr.auth.user_id and can_ban:
      form_token_path = mr.request.path + 'ban.do'
      ban_token = xsrf.GenerateToken(mr.auth.user_id, form_token_path)
      form_token_path = mr.request.path + 'banSpammer.do'
      ban_spammer_token = xsrf.GenerateToken(mr.auth.user_id, form_token_path)

    page_data = {
        'user_tab_mode': 'st2',
        'viewed_user_display_name': viewed_user_display_name,
        'viewed_user_may_be_spammer': ezt.boolean(viewed_user_may_be_spammer),
        'viewed_user_is_spammer': ezt.boolean(viewed_user_is_spammer),
        'viewed_user_is_banned': ezt.boolean(viewed_user.banned),
        'viewed_user_ignore_action_limits': (
            ezt.boolean(viewed_user.ignore_action_limits)),
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
        'last_visit_str': last_visit_str,
        'last_bounce_str': last_bounce_str,
        'vacation_message': viewed_user.vacation_message,
        'can_ban': ezt.boolean(can_ban),
        'ban_token': ban_token,
        'ban_spammer_token': ban_spammer_token
        }

    settings = framework_helpers.UserSettings.GatherUnifiedSettingsPageData(
        mr.auth.user_id, mr.viewed_user_auth.user_view, viewed_user)
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


class BanUser(servlet.Servlet):
  """Bans or un-bans a user."""

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    if not permissions.CanBan(mr, self.services):
      raise permissions.PermissionException(
          "You do not have permission to ban users.")

    framework_helpers.UserSettings.ProcessBanForm(
        mr.cnxn, self.services.user, post_data, mr.viewed_user_auth.user_id,
        mr.viewed_user_auth.user_pb)

    # TODO(jrobbins): Check all calls to FormatAbsoluteURL for include_project.
    return framework_helpers.FormatAbsoluteURL(
        mr, mr.viewed_user_auth.user_view.profile_url, include_project=False,
        saved=1, ts=int(time.time()))
