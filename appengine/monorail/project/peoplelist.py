# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display a paginated list of project members.

This page lists owners, members, and contribtors.  For each
member, we display their username, permission system role + extra
perms, and notes on their involvement in the project.
"""

import logging
import time

from third_party import ezt

from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import paginate
from framework import permissions
from framework import servlet
from framework import urls
from project import project_helpers
from project import project_views

MEMBERS_PER_PAGE = 50


class PeopleList(servlet.Servlet):
  """People list page shows a paginatied list of project members."""

  _PAGE_TEMPLATE = 'project/people-list-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PEOPLE

  def AssertBasePermission(self, mr):
    super(PeopleList, self).AssertBasePermission(mr)
    # For now, contributors who cannot view other contributors are further
    # restricted from viewing any part of the member list or detail pages.
    if not permissions.CanViewContributorList(mr):
      raise permissions.PermissionException(
          'User is not allowed to view the project people list')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    all_members = (mr.project.owner_ids +
                   mr.project.committer_ids +
                   mr.project.contributor_ids)

    with mr.profiler.Phase('gathering members on this page'):
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, all_members)
      framework_views.RevealAllEmailsToMembers(mr, users_by_id)

    # TODO(jrobbins): re-implement FindUntrustedGroups()
    untrusted_user_group_proxies = []

    with mr.profiler.Phase('gathering commitments (notes)'):
      project_commitments = self.services.project.GetProjectCommitments(
          mr.cnxn, mr.project_id)

    with mr.profiler.Phase('gathering autocomple exclusion ids'):
      acexclusion_ids = self.services.project.GetProjectAutocompleteExclusion(
          mr.cnxn, mr.project_id)

    with mr.profiler.Phase('making member views'):
      owner_views = self._MakeMemberViews(
          mr.auth.user_id, users_by_id, mr.project.owner_ids, mr.project,
          project_commitments, acexclusion_ids)
      committer_views = self._MakeMemberViews(
          mr.auth.user_id, users_by_id, mr.project.committer_ids, mr.project,
          project_commitments, acexclusion_ids)
      contributor_views = self._MakeMemberViews(
          mr.auth.user_id, users_by_id, mr.project.contributor_ids, mr.project,
          project_commitments, acexclusion_ids)
      all_member_views = owner_views + committer_views + contributor_views

    pagination = paginate.ArtifactPagination(
        mr, all_member_views, MEMBERS_PER_PAGE, urls.PEOPLE_LIST)

    offer_membership_editing = mr.perms.HasPerm(
        permissions.EDIT_PROJECT, mr.auth.user_id, mr.project)

    check_abandonment = permissions.ShouldCheckForAbandonment(mr)

    newly_added_views = [mv for mv in all_member_views
                         if str(mv.user.user_id) in mr.GetParam('new', [])]

    return {
        'pagination': pagination,
        'subtab_mode': None,
        'offer_membership_editing': ezt.boolean(offer_membership_editing),
        'initial_add_members': '',
        'initially_expand_form': ezt.boolean(False),
        'untrusted_user_groups': untrusted_user_group_proxies,
        'check_abandonment': ezt.boolean(check_abandonment),
        'total_num_owners': len(mr.project.owner_ids),
        'newly_added_views': newly_added_views,
        'is_hotlist': ezt.boolean(False),
        }

  def GatherHelpData(self, mr, page_data):
    """Return a dict of values to drive on-page user help.

    Args:
      mr: common information parsed from the HTTP request.
      page_data: Dictionary of base and page template data.

    Returns:
      A dict of values to drive on-page user help, to be added to page_data.
    """
    help_data = super(PeopleList, self).GatherHelpData(mr, page_data)
    if (mr.auth.user_id and
        not framework_bizobj.UserIsInProject(
            mr.project, mr.auth.effective_ids) and
        'how_to_join_project' not in mr.auth.user_pb.dismissed_cues):
      help_data['cue'] = 'how_to_join_project'

    return help_data

  def _MakeMemberViews(
      self, logged_in_user_id, users_by_id, member_ids, project,
      project_commitments, acexclusion_ids):
    """Return a sorted list of MemberViews for display by EZT."""
    member_views = [
        project_views.MemberView(
            logged_in_user_id, member_id, users_by_id[member_id], project,
            project_commitments, acexclusion_ids=acexclusion_ids)
        for member_id in member_ids]
    member_views.sort(key=lambda mv: mv.user.email)
    return member_views

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    permit_edit = mr.perms.HasPerm(
        permissions.EDIT_PROJECT, mr.auth.user_id, mr.project)
    if not permit_edit:
      raise permissions.PermissionException(
          'User is not permitted to edit project membership')

    if 'addbtn' in post_data:
      return self.ProcessAddMembers(mr, post_data)
    elif 'removebtn' in post_data:
      return self.ProcessRemoveMembers(mr, post_data)

  def ProcessAddMembers(self, mr, post_data):
    """Process the user's request to add members.

    Args:
      mr: common information parsed from the HTTP request.
      post_data: dictionary of form data.

    Returns:
      String URL to redirect the user to after processing.
    """
    # 1. Parse and validate user input.
    new_member_ids = project_helpers.ParseUsernames(
        mr.cnxn, self.services.user, post_data.get('addmembers'))
    role = post_data['role']

    (owner_ids, committer_ids,
     contributor_ids) = project_helpers.MembersWithGivenIDs(
        mr.project, new_member_ids, role)

    total_people = len(owner_ids) + len(committer_ids) + len(contributor_ids)
    if total_people > framework_constants.MAX_PROJECT_PEOPLE:
      mr.errors.addmembers = (
          'Too many project members.  The combined limit is %d.' %
          framework_constants.MAX_PROJECT_PEOPLE)

    # 2. Call services layer to save changes.
    if not mr.errors.AnyErrors():
      self.services.project.UpdateProjectRoles(
          mr.cnxn, mr.project.project_id,
          owner_ids, committer_ids, contributor_ids)

    # 3. Determine the next page in the UI flow.
    if mr.errors.AnyErrors():
      add_members_str = post_data.get('addmembers', '')
      self.PleaseCorrect(
          mr, initial_add_members=add_members_str, initially_expand_form=True)
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, urls.PEOPLE_LIST, saved=1, ts=int(time.time()),
          new=','.join([str(u) for u in new_member_ids]))

  def ProcessRemoveMembers(self, mr, post_data):
    """Process the user's request to remove members.

    Args:
      mr: common information parsed from the HTTP request.
      post_data: dictionary of form data.

    Returns:
      String URL to redirect the user to after processing.
    """
    # 1. Parse and validate user input.
    remove_strs = post_data.getall('remove')
    logging.info('remove_strs = %r', remove_strs)
    remove_ids = set(
        self.services.user.LookupUserIDs(mr.cnxn, remove_strs).values())
    (owner_ids, committer_ids,
     contributor_ids) = project_helpers.MembersWithoutGivenIDs(
        mr.project, remove_ids)

    # 2. Call services layer to save changes.
    self.services.project.UpdateProjectRoles(
        mr.cnxn, mr.project.project_id, owner_ids, committer_ids,
        contributor_ids)

    # 3. Determine the next page in the UI flow.
    return framework_helpers.FormatAbsoluteURL(
        mr, urls.PEOPLE_LIST, saved=1, ts=int(time.time()))
