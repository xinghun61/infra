# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""View objects to help display projects in EZT."""

import logging
import time

from third_party import ezt

from framework import framework_constants
from framework import framework_helpers
from framework import permissions
from framework import template_helpers
from framework import timestr
from framework import urls
from proto import project_pb2


class ProjectAccessView(object):
  """Object for project access information that can be easily used in EZT."""

  ACCESS_NAMES = {
      project_pb2.ProjectAccess.ANYONE: 'Anyone on the Internet',
      project_pb2.ProjectAccess.MEMBERS_ONLY: 'Project Members',
      }

  def __init__(self, project_access_enum):
    self.key = int(project_access_enum)
    self.name = self.ACCESS_NAMES[project_access_enum]


class ProjectView(template_helpers.PBProxy):
  """View object to make it easy to display a search result in EZT."""

  _MAX_SUMMARY_CHARS = 70
  _LIMITED_DESCRIPTION_CHARS = 500

  def __init__(self, pb, starred=False, now=None, num_stars=None,
               membership_desc=None):
    super(ProjectView, self).__init__(pb)

    self.limited_summary = template_helpers.FitUnsafeText(
        pb.summary, self._MAX_SUMMARY_CHARS)

    self.limited_description = template_helpers.FitUnsafeText(
        pb.description, self._LIMITED_DESCRIPTION_CHARS)

    self.state_name = str(pb.state)  # Gives the enum name
    self.relative_home_url = '/p/%s' % pb.project_name

    if now is None:
      now = time.time()

    last_full_hour = now - (now % framework_constants.SECS_PER_HOUR)
    self.cached_content_timestamp = max(
        pb.cached_content_timestamp, last_full_hour)
    self.last_updated_exists = ezt.boolean(pb.recent_activity)
    course_grain, fine_grain = timestr.GetHumanScaleDate(pb.recent_activity)
    if course_grain == 'Older':
      self.recent_activity = fine_grain
    else:
      self.recent_activity = course_grain

    self.starred = ezt.boolean(starred)

    self.num_stars = num_stars
    self.plural = '' if num_stars == 1 else 's'
    self.membership_desc = membership_desc


class MemberView(object):
  """EZT-view of details of how a person is participating in a project."""

  def __init__(
    self, logged_in_user_id, member_id, user_view, project,
    project_commitments, effective_ids=None, ac_exclusion=False,
    no_expand=False, is_group=False):
    """Initialize a MemberView with the given information.

    Args:
      logged_in_user_id: int user ID of the viewing user, or 0 for anon.
      member_id: int user ID of the project member being viewed.
      user_view: UserView object for this member.
      project: Project PB for the currently viewed project.
      project_commitments: ProjectCommitments PB for the currently viewed
          project, or None if commitments are not to be displayed.
      effective_ids: optional set of user IDs for this user, if supplied
          we show the highest role that they have via any group membership.
      ac_exclusion: True when this member should not be in autocomplete.
      no_expand: True for user groups that should not expand when generating
          autocomplete options.
      is_group: True if this user is actually a user group.
    """
    self.viewing_self = ezt.boolean(logged_in_user_id == member_id)

    self.user = user_view
    member_qs_param = user_view.user_id
    self.detail_url = '/p/%s%s?u=%s' % (
        project.project_name, urls.PEOPLE_DETAIL, member_qs_param)
    self.role = framework_helpers.GetRoleName(
        effective_ids or {member_id}, project)
    self.extra_perms = permissions.GetExtraPerms(project, member_id)
    self.notes = None
    if project_commitments is not None:
      for commitment in project_commitments.commitments:
        if commitment.member_id == member_id:
          self.notes = commitment.notes
          break

    # Attributes needed by table_view_helpers.py
    self.labels = []
    self.derived_labels = []

    self.ac_include = ezt.boolean(not ac_exclusion)
    self.ac_expand = ezt.boolean(not no_expand)

    self.is_group = ezt.boolean(is_group)
    self.is_service_account = ezt.boolean(framework_helpers.IsServiceAccount(
        self.user.email))
