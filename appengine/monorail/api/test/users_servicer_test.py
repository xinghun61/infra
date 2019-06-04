# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the users servicer."""

import unittest

import mox
from components.prpc import codes
from components.prpc import context
from components.prpc import server

from api import users_servicer
from api.api_proto import common_pb2
from api.api_proto import users_pb2
from api.api_proto import user_objects_pb2
from framework import authdata
from framework import exceptions
from framework import monorailcontext
from framework import permissions
from proto import project_pb2
from proto import tracker_pb2
from proto import user_pb2
from testing import fake
from services import service_manager


class UsersServicerTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        user_star=fake.UserStarService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        project_star=fake.ProjectStarService(),
        features=fake.FeaturesService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.user = self.services.user.TestAddUser('owner@example.com', 111)
    self.user_2 = self.services.user.TestAddUser('test2@example.com', 222)
    self.group1_id = self.services.usergroup.CreateGroup(
        self.cnxn, self.services, 'group1@test.com', 'anyone')
    self.group2_id = self.services.usergroup.CreateGroup(
        self.cnxn, self.services, 'group2@test.com', 'anyone')
    self.services.usergroup.UpdateMembers(
        self.cnxn, self.group1_id, [111], 'member')
    self.services.usergroup.UpdateMembers(
        self.cnxn, self.group2_id, [222, 111], 'owner')
    self.users_svcr = users_servicer.UsersServicer(
        self.services, make_rate_limiter=False)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(codes.StatusCode.OK)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def CallWrapped(self, wrapped_handler, *args, **kwargs):
    return wrapped_handler.wrapped(self.users_svcr, *args, **kwargs)

  def testGetMemberships(self):
    request = users_pb2.GetMembershipsRequest(
        user_ref=common_pb2.UserRef(
            display_name='owner@example.com', user_id=111))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    response = self.CallWrapped(self.users_svcr.GetMemberships, mc, request)
    expected_group_refs = [
        common_pb2.UserRef(
            display_name='group1@test.com', user_id=self.group1_id),
        common_pb2.UserRef(
            display_name='group2@test.com', user_id=self.group2_id)
    ]

    self.assertItemsEqual(expected_group_refs, response.group_refs)

  def testGetMemberships_NonExistentUser(self):
    request = users_pb2.GetMembershipsRequest(
        user_ref=common_pb2.UserRef(
            display_name='ghost@example.com', user_id=888)
    )

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='')

    with self.assertRaises(exceptions.NoSuchUserException):
      self.CallWrapped(self.users_svcr.GetMemberships, mc, request)

  def testGetUser(self):
    """We can get a user by email address."""
    user_ref = common_pb2.UserRef(display_name='test2@example.com')
    request = users_pb2.GetUserRequest(user_ref=user_ref)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.users_svcr.GetUser, mc, request)
    self.assertEqual(response.email, 'test2@example.com')
    self.assertEqual(response.user_id, 222)
    self.assertFalse(response.is_site_admin)

    self.user_2.is_site_admin = True
    response = self.CallWrapped(
        self.users_svcr.GetUser, mc, request)
    self.assertTrue(response.is_site_admin)

  def testListReferencedUsers(self):
    """We can get all valid users by email addresses."""
    request = users_pb2.ListReferencedUsersRequest(
        # we ignore emails that are empty or belong to non-existent users.
        user_refs=[
            common_pb2.UserRef(display_name='test2@example.com'),
            common_pb2.UserRef(display_name='ghost@example.com'),
            common_pb2.UserRef(display_name=''),
            common_pb2.UserRef()])
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.users_svcr.ListReferencedUsers, mc, request)
    self.assertEqual(len(response.users), 1)
    self.assertEqual(response.users[0].user_id, 222)

  def testListReferencedUsers_Deprecated(self):
    """We can get all valid users by email addresses."""
    request = users_pb2.ListReferencedUsersRequest(
        # we ignore emails that are empty or belong to non-existent users.
        emails=[
            'test2@example.com',
            'ghost@example.com',
            ''])
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.users_svcr.ListReferencedUsers, mc, request)
    self.assertEqual(len(response.users), 1)
    self.assertEqual(response.users[0].user_id, 222)

  def CallGetStarCount(self):
    request = users_pb2.GetUserStarCountRequest(
        user_ref=common_pb2.UserRef(user_id=222))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.users_svcr.GetUserStarCount, mc, request)
    return response.star_count

  def CallStar(self, requester='owner@example.com', starred=True):
    request = users_pb2.StarUserRequest(
        user_ref=common_pb2.UserRef(user_id=222), starred=starred)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=requester)
    response = self.CallWrapped(
        self.users_svcr.StarUser, mc, request)
    return response.star_count

  def testStarCount_Normal(self):
    self.assertEqual(0, self.CallGetStarCount())
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

  def testStarCount_StarTwiceSameUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

  def testStarCount_StarTwiceDifferentUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(2, self.CallStar(requester='test2@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceSameUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceDifferentUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(2, self.CallStar(requester='test2@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

    self.assertEqual(1, self.CallStar(starred=False))
    self.assertEqual(
        0, self.CallStar(requester='test2@example.com', starred=False))
    self.assertEqual(0, self.CallGetStarCount())

  def testSetExpandPermsPreference_KeepOpen(self):
    request = users_pb2.SetExpandPermsPreferenceRequest(expand_perms=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.users_svcr.SetExpandPermsPreference, mc, request)

    user = self.services.user.GetUser(self.cnxn, self.user.user_id)
    self.assertTrue(user.keep_people_perms_open)

  def testSetExpandPermsPreference_DontKeepOpen(self):
    request = users_pb2.SetExpandPermsPreferenceRequest(expand_perms=False)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.users_svcr.SetExpandPermsPreference, mc, request)

    user = self.services.user.GetUser(self.cnxn, self.user.user_id)
    self.assertFalse(user.keep_people_perms_open)

  def testGetUserSavedQueries_Anon(self):
    """Anon has empty saved queries."""
    request = users_pb2.GetSavedQueriesRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=None)
    response = self.CallWrapped(self.users_svcr.GetSavedQueries, mc, request)

    self.assertEqual(0, len(response.saved_queries))

  def testGetUserSavedQueries_Mine(self):
    """See your own queries."""
    self.services.features.UpdateUserSavedQueries(self.cnxn, 111, [
      tracker_pb2.SavedQuery(query_id=101, name='test', query='owner:me'),
      tracker_pb2.SavedQuery(query_id=202, name='hello', query='world',
          executes_in_project_ids=[987])
    ])
    request = users_pb2.GetUserPrefsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.users_svcr.GetSavedQueries, mc, request)

    self.assertEqual(2, len(response.saved_queries))

    self.assertEqual('test', response.saved_queries[0].name)
    self.assertEqual('owner:me', response.saved_queries[0].query)
    self.assertEqual('hello', response.saved_queries[1].name)
    self.assertEqual('world', response.saved_queries[1].query)
    self.assertEqual(['proj'], response.saved_queries[1].project_names)


  def testGetUserSavedQueries_Other_Allowed(self):
    """See other people's queries if you're an admin."""
    self.services.features.UpdateUserSavedQueries(self.cnxn, 111, [
      tracker_pb2.SavedQuery(query_id=101, name='test', query='owner:me'),
      tracker_pb2.SavedQuery(query_id=202, name='hello', query='world',
          executes_in_project_ids=[987])
    ])
    self.user_2.is_site_admin = True

    request = users_pb2.GetSavedQueriesRequest()
    request.user_ref.display_name = 'owner@example.com'

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='test2@example.com')

    response = self.CallWrapped(self.users_svcr.GetSavedQueries, mc, request)

    self.assertEqual(2, len(response.saved_queries))

    self.assertEqual('test', response.saved_queries[0].name)
    self.assertEqual('owner:me', response.saved_queries[0].query)
    self.assertEqual('hello', response.saved_queries[1].name)
    self.assertEqual('world', response.saved_queries[1].query)
    self.assertEqual(['proj'], response.saved_queries[1].project_names)

  def testGetUserSavedQueries_Other_Denied(self):
    """Can't see other people's queries unless you're an admin."""
    self.services.features.UpdateUserSavedQueries(self.cnxn, 111, [
      tracker_pb2.SavedQuery(query_id=101, name='test', query='owner:me'),
      tracker_pb2.SavedQuery(query_id=202, name='hello', query='world',
          executes_in_project_ids=[987])
    ])

    request = users_pb2.GetSavedQueriesRequest()
    request.user_ref.display_name = 'owner@example.com'

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='test2@example.com')

    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.users_svcr.GetSavedQueries, mc, request)

  def testGetUserPrefs_Anon(self):
    """Anon always has empty prefs."""
    request = users_pb2.GetUserPrefsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=None)
    response = self.CallWrapped(self.users_svcr.GetUserPrefs, mc, request)

    self.assertEqual(0, len(response.prefs))

  def testGetUserPrefs_Mine_Empty(self):
    """User who never set any pref gets empty prefs."""
    request = users_pb2.GetUserPrefsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.users_svcr.GetUserPrefs, mc, request)

    self.assertEqual(0, len(response.prefs))

  def testGetUserPrefs_Mine_Some(self):
    """User who set a pref gets it back."""
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    request = users_pb2.GetUserPrefsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.users_svcr.GetUserPrefs, mc, request)

    self.assertEqual(1, len(response.prefs))
    self.assertEqual('code_font', response.prefs[0].name)
    self.assertEqual('true', response.prefs[0].value)

  def testGetUserPrefs_Other_Allowed(self):
    """A site admin can read another user's prefs."""
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    self.user_2.is_site_admin = True

    request = users_pb2.GetUserPrefsRequest()
    request.user_ref.display_name = 'owner@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='test2@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.users_svcr.GetUserPrefs, mc, request)

    self.assertEqual(1, len(response.prefs))
    self.assertEqual('code_font', response.prefs[0].name)
    self.assertEqual('true', response.prefs[0].value)

  def testGetUserPrefs_Other_Denied(self):
    """A non-admin cannot read another user's prefs."""
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    # user2 is not a site admin.

    request = users_pb2.GetUserPrefsRequest()
    request.user_ref.display_name = 'owner@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='test2@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.users_svcr.GetUserPrefs, mc, request)

  def testSetUserPrefs_Anon(self):
    """Anon cannot set prefs."""
    request = users_pb2.SetUserPrefsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=None)
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.users_svcr.SetUserPrefs, mc, request)

  def testSetUserPrefs_Mine_Empty(self):
    """Setting zero prefs is a no-op.."""
    request = users_pb2.SetUserPrefsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.users_svcr.SetUserPrefs, mc, request)

    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(0, len(prefs_after.prefs))

  def testSetUserPrefs_Mine_Add(self):
    """User can set a preference for the first time."""
    request = users_pb2.SetUserPrefsRequest(
        prefs=[user_objects_pb2.UserPrefValue(name='code_font', value='true')])
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.users_svcr.SetUserPrefs, mc, request)

    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(1, len(prefs_after.prefs))
    self.assertEqual('code_font', prefs_after.prefs[0].name)
    self.assertEqual('true', prefs_after.prefs[0].value)

  def testSetUserPrefs_Mine_Overwrite(self):
    """User can change the value of a pref."""
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    request = users_pb2.SetUserPrefsRequest(
        prefs=[user_objects_pb2.UserPrefValue(name='code_font', value='false')])
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.users_svcr.SetUserPrefs, mc, request)

    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(1, len(prefs_after.prefs))
    self.assertEqual('code_font', prefs_after.prefs[0].name)
    self.assertEqual('false', prefs_after.prefs[0].value)

  def testSetUserPrefs_Other_Allowed(self):
    """A site admin can update another user's prefs."""
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    self.user_2.is_site_admin = True

    request = users_pb2.SetUserPrefsRequest(
        prefs=[user_objects_pb2.UserPrefValue(name='code_font', value='false')])
    request.user_ref.display_name = 'owner@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='test2@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    self.CallWrapped(self.users_svcr.SetUserPrefs, mc, request)

    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(1, len(prefs_after.prefs))
    self.assertEqual('code_font', prefs_after.prefs[0].name)
    self.assertEqual('false', prefs_after.prefs[0].value)

  def testSetUserPrefs_Other_Denied(self):
    """A non-admin cannot set another user's prefs."""
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    # user2 is not a site admin.

    request = users_pb2.SetUserPrefsRequest(
        prefs=[user_objects_pb2.UserPrefValue(name='code_font', value='false')])
    request.user_ref.display_name = 'owner@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='test2@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.users_svcr.SetUserPrefs, mc, request)

    # Regardless of any exception, the preferences remain unchanged.
    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(1, len(prefs_after.prefs))
    self.assertEqual('code_font', prefs_after.prefs[0].name)
    self.assertEqual('true', prefs_after.prefs[0].value)

  def testInviteLinkedParent_NotFound(self):
    """Reject attempt to invite a user that does not exist."""
    self.services.user.TestAddUser('user@google.com', 333)
    request = users_pb2.InviteLinkedParentRequest(
        email='who@chromium.org')  # Does not exist.
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='who@google.com')
    with self.assertRaises(exceptions.NoSuchUserException):
      self.CallWrapped(self.users_svcr.InviteLinkedParent, mc, request)

  def testInviteLinkedParent_Normal(self):
    """We can invite accounts to link when all criteria are met."""
    self.services.user.TestAddUser('user@google.com', 333)
    self.services.user.TestAddUser('user@chromium.org', 444)
    request = users_pb2.InviteLinkedParentRequest(
        email='user@google.com')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@chromium.org')
    self.CallWrapped(self.users_svcr.InviteLinkedParent, mc, request)

    (invite_as_parent, invite_as_child
     ) = self.services.user.GetPendingLinkedInvites(self.cnxn, 333)
    self.assertEqual([444], invite_as_parent)
    self.assertEqual([], invite_as_child)
    (invite_as_parent, invite_as_child
     ) = self.services.user.GetPendingLinkedInvites(self.cnxn, 444)
    self.assertEqual([], invite_as_parent)
    self.assertEqual([333], invite_as_child)

  def testAcceptLinkedChild_NotFound(self):
    """Reject attempt to link a user that does not exist."""
    self.services.user.TestAddUser('user@google.com', 333)
    request = users_pb2.AcceptLinkedChildRequest(
        email='who@chromium.org')  # Does not exist.
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='who@google.com')
    with self.assertRaises(exceptions.NoSuchUserException):
      self.CallWrapped(self.users_svcr.AcceptLinkedChild, mc, request)

  def testAcceptLinkedChild_NoInvite(self):
    """Reject attempt to link accounts when there was no invite."""
    self.services.user.TestAddUser('user@google.com', 333)
    self.services.user.TestAddUser('user@chromium.org', 444)
    request = users_pb2.AcceptLinkedChildRequest(
        email='user@chromium.org')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@google.com')
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.users_svcr.AcceptLinkedChild, mc, request)

  def testAcceptLinkedChild_Normal(self):
    """We can linke accounts when all criteria are met."""
    parent = self.services.user.TestAddUser('user@google.com', 333)
    child = self.services.user.TestAddUser('user@chromium.org', 444)
    self.services.user.InviteLinkedParent(
        self.cnxn, parent.user_id, child.user_id)
    request = users_pb2.AcceptLinkedChildRequest(
        email='user@chromium.org')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@google.com')
    self.CallWrapped(self.users_svcr.AcceptLinkedChild, mc, request)

    self.assertEqual(parent.user_id, child.linked_parent_id)
    self.assertIn(child.user_id, parent.linked_child_ids)

  def testUnlinkAccounts_NotFound(self):
    """Reject attempt to unlink a user that does not exist or unspecified."""
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    request = users_pb2.UnlinkAccountsRequest(
        parent=common_pb2.UserRef(display_name='who@chromium.org'),
        child=common_pb2.UserRef(display_name='owner@example.com'))
    with self.assertRaises(exceptions.NoSuchUserException):
      self.CallWrapped(self.users_svcr.UnlinkAccounts, mc, request)

    request = users_pb2.UnlinkAccountsRequest(
        parent=common_pb2.UserRef(display_name='owner@example.com'),
        child=common_pb2.UserRef(display_name='who@google.com'))
    with self.assertRaises(exceptions.NoSuchUserException):
      self.CallWrapped(self.users_svcr.UnlinkAccounts, mc, request)

    request = users_pb2.UnlinkAccountsRequest(
        parent=common_pb2.UserRef(display_name='owner@example.com'))
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.users_svcr.UnlinkAccounts, mc, request)

    request = users_pb2.UnlinkAccountsRequest(
        child=common_pb2.UserRef(display_name='owner@example.com'))
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.users_svcr.UnlinkAccounts, mc, request)

  def testUnlinkAccounts_Normal(self):
    """Users can unlink their accounts."""
    self.services.user.linked_account_rows = [(111, 222)]
    request = users_pb2.UnlinkAccountsRequest(
        parent=common_pb2.UserRef(display_name='owner@example.com'),
        child=common_pb2.UserRef(display_name='test2@example.com'))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    self.CallWrapped(self.users_svcr.UnlinkAccounts, mc, request)

    self.assertEqual([], self.services.user.linked_account_rows)

  def AddUserProjects(self, user_id):
    project_states = {
        'live': project_pb2.ProjectState.LIVE,
        'archived': project_pb2.ProjectState.ARCHIVED,
        'deletable': project_pb2.ProjectState.DELETABLE}

    for name, state in project_states.iteritems():
      self.services.project.TestAddProject(
          'owner-%s-%s' % (name, user_id), state=state, owner_ids=[user_id])
      self.services.project.TestAddProject(
          'committer-%s-%s' % (name, user_id), state=state,\
          committer_ids=[user_id])
      contributor = self.services.project.TestAddProject(
          'contributor-%s-%s' % (name, user_id), state=state)
      contributor.contributor_ids = [user_id]

    members_only = self.services.project.TestAddProject(
        'members-only-' + str(user_id), owner_ids=[user_id])
    members_only.access = project_pb2.ProjectAccess.MEMBERS_ONLY

  def testGetUsersProjects(self):
    self.user = self.services.user.TestAddUser('test3@example.com', 333)
    self.services.project_star.SetStar(
        self.cnxn, self.project.project_id, 222, True)
    self.project.committer_ids.extend([222])

    self.AddUserProjects(222)
    self.AddUserProjects(333)

    request = users_pb2.GetUsersProjectsRequest(user_refs=[
        common_pb2.UserRef(display_name='test2@example.com'),
        common_pb2.UserRef(display_name='test3@example.com')])
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='test2@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.users_svcr.GetUsersProjects, mc, request)

    self.assertEqual([
        user_objects_pb2.UserProjects(
            user_ref=common_pb2.UserRef(display_name='test2@example.com'),
            owner_of=['members-only-222', 'owner-live-222'],
            member_of=['committer-live-222', 'proj'],
            contributor_to=['contributor-live-222'],
            starred_projects=['proj']),
        user_objects_pb2.UserProjects(
            user_ref=common_pb2.UserRef(display_name='test3@example.com'),
            owner_of=['owner-live-333'],
            member_of=['committer-live-333'],
            contributor_to=['contributor-live-333'])],
        list(response.users_projects))

  def testGetUsersProjects_NoUserRefs(self):
    request = users_pb2.GetUsersProjectsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='test2@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.users_svcr.GetUsersProjects, mc, request)
    self.assertEqual([], list(response.users_projects))
