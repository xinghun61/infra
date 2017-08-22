# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display details about each project member."""

import logging
import time

from third_party import ezt

from framework import exceptions
from framework import framework_bizobj
from framework import framework_helpers
from framework import framework_views
from framework import jsonfeed
from framework import permissions
from framework import servlet
from framework import template_helpers
from framework import urls
from project import project_helpers
from project import project_views
from services import user_svc

CHECKBOX_PERMS = [
    permissions.VIEW,
    permissions.COMMIT,
    permissions.CREATE_ISSUE,
    permissions.ADD_ISSUE_COMMENT,
    permissions.EDIT_ISSUE,
    permissions.EDIT_ISSUE_OWNER,
    permissions.EDIT_ISSUE_SUMMARY,
    permissions.EDIT_ISSUE_STATUS,
    permissions.EDIT_ISSUE_CC,
    permissions.DELETE_ISSUE,
    permissions.DELETE_OWN,
    permissions.DELETE_ANY,
    permissions.EDIT_ANY_MEMBER_NOTES,
    permissions.MODERATE_SPAM,
    ]


class PeopleDetail(servlet.Servlet):
  """People detail page documents one partipant's involvement in a project."""

  _PAGE_TEMPLATE = 'project/people-detail-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PEOPLE

  def AssertBasePermission(self, mr):
    """Check that the user is allowed to access this servlet."""
    super(PeopleDetail, self).AssertBasePermission(mr)
    member_id = self.ValidateMemberID(mr.cnxn, mr.specified_user_id, mr.project)
    # For now, contributors who cannot view other contributors are further
    # restricted from viewing any part of the member list or detail pages.
    if (not permissions.CanViewContributorList(mr) and
        member_id != mr.auth.user_id):
      raise permissions.PermissionException(
          'User is not allowed to view other people\'s details')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""

    member_id = self.ValidateMemberID(mr.cnxn, mr.specified_user_id, mr.project)
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user, [member_id])
    framework_views.RevealAllEmailsToMembers(mr, users_by_id)

    project_commitments = self.services.project.GetProjectCommitments(
        mr.cnxn, mr.project_id)
    acexclusion_ids = self.services.project.GetProjectAutocompleteExclusion(
        mr.cnxn, mr.project_id)
    member_view = project_views.MemberView(
        mr.auth.user_id, member_id, users_by_id[member_id], mr.project,
        project_commitments, acexclusion_ids=acexclusion_ids)

    member_user = self.services.user.GetUser(mr.cnxn, member_id)
    # This ignores indirect memberships, which is ok because we are viewing
    # the page for a member directly involved in the project
    role_perms = permissions.GetPermissions(
        member_user, {member_id}, mr.project)

    # TODO(jrobbins): clarify in the UI which permissions are built-in to
    # the user's direct role, vs. which are granted via a group membership,
    # vs. which ones are extra_perms that have been added specifically for
    # this user.
    member_perms = template_helpers.EZTItem()
    for perm in CHECKBOX_PERMS:
      setattr(member_perms, perm,
              ezt.boolean(role_perms.HasPerm(perm, member_id, mr.project)))

    displayed_extra_perms = [perm for perm in member_view.extra_perms
                             if perm not in CHECKBOX_PERMS]

    viewing_self = mr.auth.user_id == member_id
    warn_abandonment = (viewing_self and
                        permissions.ShouldCheckForAbandonment(mr))

    return {
        'subtab_mode': None,
        'member': member_view,
        'role_perms': role_perms,
        'member_perms': member_perms,
        'displayed_extra_perms': displayed_extra_perms,
        'offer_edit_perms': ezt.boolean(self.CanEditPerms(mr)),
        'offer_edit_member_notes': ezt.boolean(
            self.CanEditMemberNotes(mr, member_id)),
        'offer_remove_role': ezt.boolean(self.CanRemoveRole(mr, member_id)),
        'expand_perms': ezt.boolean(mr.auth.user_pb.keep_people_perms_open),
        'warn_abandonment': ezt.boolean(warn_abandonment),
        'total_num_owners': len(mr.project.owner_ids),
        }

  def ValidateMemberID(self, cnxn, member_id, project):
    """Lookup a project member by user_id.

    Args:
      cnxn: connection to SQL database.
      member_id: int user_id, same format as user profile page.
      project: the current Project PB.

    Returns:
      The user ID of the project member. Raises an exception if the username
      cannot be looked up, or if that user is not in the project.
    """
    if not member_id:
      self.abort(404, 'project member not specified')

    member_username = None
    try:
      member_username = self.services.user.LookupUserEmail(cnxn, member_id)
    except user_svc.NoSuchUserException:
      logging.info('user_id %s not found', member_id)

    if not member_username:
      logging.info('There is no such user id %r', member_id)
      self.abort(404, 'project member not found')

    if not framework_bizobj.UserIsInProject(project, {member_id}):
      logging.info('User %r is not a member of %r',
                   member_username, project.project_name)
      self.abort(404, 'project member not found')

    return member_id

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    # 1. Parse and validate user input.
    user_id, role, extra_perms, notes, ac_exclusion = (
        self.ParsePersonData(mr, post_data))
    member_id = self.ValidateMemberID(mr.cnxn, user_id, mr.project)

    # 2. Call services layer to save changes.
    if 'remove' in post_data:
      self.ProcessRemove(mr, member_id)
    else:
      self.ProcessSave(mr, role, extra_perms, notes, member_id, ac_exclusion)

    # 3. Determine the next page in the UI flow.
    if 'remove' in post_data:
      return framework_helpers.FormatAbsoluteURL(
          mr, urls.PEOPLE_LIST, saved=1, ts=int(time.time()))
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, urls.PEOPLE_DETAIL, u=user_id, saved=1, ts=int(time.time()))

  def ProcessRemove(self, mr, member_id):
    """Process the posted form when the user pressed 'Remove'."""
    if not self.CanRemoveRole(mr, member_id):
      raise permissions.PermissionException(
          'User is not allowed to remove this member from the project')

    self.RemoveRole(mr.cnxn, mr.project, member_id)

  def ProcessSave(self, mr, role, extra_perms, notes, member_id, ac_exclusion):
    """Process the posted form when the user pressed 'Save'."""
    if (not self.CanEditPerms(mr) and
        not self.CanEditMemberNotes(mr, member_id)):
      raise permissions.PermissionException(
          'User is not allowed to edit people in this project')

    if self.CanEditPerms(mr):
      self.services.project.UpdateExtraPerms(
          mr.cnxn, mr.project_id, member_id, extra_perms)
      self.UpdateRole(mr.cnxn, mr.project, role, member_id)

    if self.CanEditMemberNotes(mr, member_id):
      self.services.project.UpdateCommitments(
          mr.cnxn, mr.project_id, member_id, notes)

    if self.CanEditPerms(mr):
      self.services.project.UpdateProjectAutocompleteExclusion(
          mr.cnxn, mr.project_id, member_id, ac_exclusion)

  def CanEditMemberNotes(self, mr, member_id):
    """Return true if the logged in user can edit the current user's notes."""
    return (self.CheckPerm(mr, permissions.EDIT_ANY_MEMBER_NOTES) or
            member_id == mr.auth.user_id)

  def CanEditPerms(self, mr):
    """Return true if the logged in user can edit the current user's perms."""
    return self.CheckPerm(mr, permissions.EDIT_PROJECT)

  def CanRemoveRole(self, mr, member_id):
    """Return true if the logged in user can remove the current user's role."""
    return (self.CheckPerm(mr, permissions.EDIT_PROJECT) or
            member_id == mr.auth.user_id)

  def ParsePersonData(self, mr, post_data):
    """Parse the POST data for a project member.

    Args:
      mr: common information parsed from the user's request.
      post_data: dictionary of lists of values for each HTML
          form field.

    Returns:
      A tuple with user_id, role, extra_perms, and notes.
    """
    if not mr.specified_user_id:
      raise exceptions.InputException('Field user_id is missing')

    role = post_data.get('role', '').lower()
    extra_perms = []
    for ep in post_data.getall('extra_perms'):
      perm = framework_bizobj.CanonicalizeLabel(ep)
      # Perms with leading underscores are reserved.
      perm = perm.strip('_')
      if perm:
        extra_perms.append(perm)

    notes = post_data.get('notes', '').strip()
    ac_exclusion = post_data.get('ac_exclude', '')
    return mr.specified_user_id, role, extra_perms, notes, bool(ac_exclusion)

  def RemoveRole(self, cnxn, project, member_id):
    """Remove the given member from the project."""
    (owner_ids, committer_ids,
     contributor_ids) = project_helpers.MembersWithoutGivenIDs(
         project, {member_id})
    self.services.project.UpdateProjectRoles(
        cnxn, project.project_id, owner_ids, committer_ids, contributor_ids)

  def UpdateRole(self, cnxn, project, role, member_id):
    """If the user's role was changed, update that in the Project."""
    if not role:
      return  # Role was not in the form data

    if role == framework_helpers.GetRoleName({member_id}, project).lower():
      return  # No change needed

    (owner_ids, committer_ids,
     contributor_ids) = project_helpers.MembersWithGivenIDs(
         project, {member_id}, role)

    self.services.project.UpdateProjectRoles(
        cnxn, project.project_id, owner_ids, committer_ids, contributor_ids)


class PagePrefs(jsonfeed.JsonFeed):
  """Remember a user pref for hide/show state of people permissions."""

  def HandleRequest(self, mr):
    """Store the logged in user's preference for the people detail page."""
    expanded = bool(mr.GetIntParam('perms_expanded'))
    logging.info('setting expanded: %r', expanded)

    if mr.auth.user_id:
      self.services.user.UpdateUserSettings(
          mr.cnxn, mr.auth.user_id, mr.auth.user_pb,
          keep_people_perms_open=expanded)

    return {'expanded': expanded}
