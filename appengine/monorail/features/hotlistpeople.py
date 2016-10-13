# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to implement the hotlistpeople page and related forms."""

import time

from third_party import ezt

from features import hotlist_helpers
from features import hotlist_views
from framework import framework_helpers
from framework import framework_views
from framework import paginate
from framework import permissions
from framework import servlet
from framework import urls
from project import project_helpers

MEMBERS_PER_PAGE = 50


class HotlistPeopleList(servlet.Servlet):
  _PAGE_TEMPLATE = 'project/people-list-page.ezt'
  # Note: using the project's peoplelist page template. minor edits were
  # to make it compatible with HotlistPeopleList

  def AssertBasePermission(self, mr):
    super(HotlistPeopleList, self).AssertBasePermission(mr)
    if not permissions.CanViewHotlist(mr.auth.effective_ids, mr.hotlist):
      raise permissions.PermissionException(
          'User is now allowed to view the hotlist people list')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    all_members = (mr.hotlist.owner_ids +
                   mr.hotlist.editor_ids + mr.hotlist.follower_ids)

    with self.profiler.Phase('gathering members on this page'):
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, all_members)
      framework_views.RevealAllEmailsToMembers(mr, users_by_id)

    untrusted_user_group_proxies = []
    # TODO(jojwang): implement FindUntrustedGroups()

    with self.profiler.Phase('making member views'):
      owner_views = self._MakeMemberViews(mr, mr.hotlist.owner_ids)
      editor_views = self._MakeMemberViews(mr, mr.hotlist.editor_ids)
      follower_views = self._MakeMemberViews(mr, mr.hotlist.follower_ids)
      all_member_views = owner_views + editor_views + follower_views

    pagination = paginate.ArtifactPagination(
        mr, all_member_views, MEMBERS_PER_PAGE, urls.HOTLIST_PEOPLE)

    offer_membership_editing = permissions.CanAdministerHotlist(
        mr.auth.effective_ids, mr.hotlist)

    newly_added_views = [mv for mv in all_member_views
                         if str(mv.user.user_id) in mr.GetParam('new', [])]

    return {
        'is_hotlist': ezt.boolean(True),
        'untrusted_user_groups': untrusted_user_group_proxies,
        'pagination': pagination,
        'initial_add_members': '',
        'subtab_mode': None,
        'initially_expand_form': ezt.boolean(False),
        'newly_added_views': newly_added_views,
        'offer_membership_editing': ezt.boolean(offer_membership_editing),
        'total_num_owners': len(mr.hotlist.owner_ids),
        'check_abandonment': ezt.boolean(False),
        # TODO(jojwang): implement ShouldCheckForHotlistAbandonment for
        # check_abandonment
        }

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    permit_edit = permissions.CanAdministerHotlist(
        mr.auth.effective_ids, mr.hotlist)
    if not permit_edit:
      raise permissions.PermissionException(
          'User is not permitted to edit hotlist membership')
    if 'addbtn' in post_data:
      return self.ProcessAddMembers(mr, post_data)
    # TODO(jojwang): add removebtn, changebtn, transferbtn

  def _MakeMemberViews(self, mr, member_ids):
    """Return a sorted list of MemberViews for display by EZT."""
    member_views = [hotlist_views.MemberView(
        mr.auth.user_id, member_id, framework_views.MakeUserView(
            mr.cnxn, self.services.user, member_id),
        mr.hotlist) for member_id in member_ids]
    member_views.sort(key=lambda mv: mv.user.email)
    return member_views

  def ProcessAddMembers(self, mr, post_data):
    """Process the user's request to add members.

    Args:
      mr: common information parsed from the HTTP request.
      post_data: dictionary of form data

    Returns:
      String URL to redirect the user to after processing
    """
    # NOTE: using project_helpers function
    new_member_ids = project_helpers.ParseUsernames(
        mr.cnxn, self.services.user, post_data.get('addmembers'))
    # add mr.error when email is invalid
    # role = post_data['role']

    # TODO(jojwang): implement self.services.features.UpdateHotlistRoles
    # owner_ids, editor_ids, follower_ids =
    # hotlist_helpers.MembersWithGiven_ids(
    #    mr.hotlist, new_member_ids, role)

    # TODO(jojwang): implement MAX_HOTLIST_PEOPLE

    if mr.errors.AnyErrors():
      add_members_str = post_data.get('addmembers', '')
      self.PleaseCorrect(
          mr, initial_add_members=add_members_str, initially_expand_form=True)
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, '/u/%s/hotlists/%s%s' % (
              mr.auth.user_id, mr.hotlist_id, urls.HOTLIST_PEOPLE),
          saved=1, ts=int(time.time()),
          new=','.join([str(u) for u in new_member_ids]),
          include_project=False)

    # TODO(jojwang): ProcessRemoveMembers
    # TODO(jojwang): ProcessChangeRoles
    # TODO(jojwang): ProcessTransferOwnership

# TODO(jojwang): add _MakeMemberViews(self, logged_in_user_id
# users_by_id, member_ids, hotlists):
