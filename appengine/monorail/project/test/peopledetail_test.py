# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the people detail page."""

import logging

import unittest

import webapp2

from framework import exceptions
from framework import monorailrequest
from framework import permissions
from project import peopledetail
from proto import project_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class PeopleDetailTest(unittest.TestCase):

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService())
    services.user.TestAddUser('jrobbins', 111L)
    services.user.TestAddUser('jrobbins@jrobbins.org', 333L)
    services.user.TestAddUser('jrobbins@chromium.org', 555L)
    services.user.TestAddUser('imso31337@gmail.com', 999L)
    self.project = services.project.TestAddProject('proj')
    self.project.owner_ids.extend([111L, 222L])
    self.project.committer_ids.extend([333L, 444L])
    self.project.contributor_ids.extend([555L])
    self.servlet = peopledetail.PeopleDetail('req', 'res', services=services)

  def VerifyAccess(self, exception_expected):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.servlet.AssertBasePermission(mr)
    # Owner never raises PermissionException.

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=333',
        project=self.project,
        perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    self.servlet.AssertBasePermission(mr)
    # Committer never raises PermissionException.

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=555',
        project=self.project,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    if exception_expected:
      self.assertRaises(permissions.PermissionException,
                        self.servlet.AssertBasePermission, mr)
    else:
      self.servlet.AssertBasePermission(mr)
      # No PermissionException raised

    # Sign-out users
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=555',
        project=self.project,
        perms=permissions.READ_ONLY_PERMISSIONSET)
    if exception_expected:
      self.assertRaises(permissions.PermissionException,
                        self.servlet.AssertBasePermission, mr)
    else:
      self.servlet.AssertBasePermission(mr)

    # Non-membr users
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=555',
        project=self.project,
        perms=permissions.USER_PERMISSIONSET)
    if exception_expected:
      self.assertRaises(permissions.PermissionException,
                        self.servlet.AssertBasePermission, mr)
    else:
      self.servlet.AssertBasePermission(mr)

  def testAssertBasePermission_Normal(self):
    self.VerifyAccess(False)

  def testAssertBasePermission_HubSpoke(self):
    self.project.only_owners_see_contributors = True
    self.VerifyAccess(True)

  def testAssertBasePermission_HubSpokeViewingSelf(self):
    self.project.only_owners_see_contributors = True
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=333',
        project=self.project,
        perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    mr.auth.user_id = 333L
    self.servlet.AssertBasePermission(mr)
    # No PermissionException raised

  def testGatherPageData(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    mr.auth = monorailrequest.AuthData()
    page_data = self.servlet.GatherPageData(mr)
    self.assertFalse(page_data['warn_abandonment'])
    self.assertEquals(2, page_data['total_num_owners'])
    # TODO(jrobbins): fill in tests for all other aspects.

  def testValidateMemberID(self):
    # We can validate owners
    self.assertEquals(
        111L,
        self.servlet.ValidateMemberID('fake cnxn', 111, self.project))

    # We can parse members
    self.assertEquals(
        333L,
        self.servlet.ValidateMemberID(
            'fake cnxn', 333, self.project))

    # 404 for user that does not exist
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.ValidateMemberID('fake cnxn', 8933, self.project)
    self.assertEquals(404, cm.exception.code)

    # 404 for valid user that is not in this project
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.ValidateMemberID('fake cnxn', 999, self.project)
    self.assertEquals(404, cm.exception.code)

  def testParsePersonData_BadPost(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail',
        project=self.project)
    post_data = fake.PostData()
    with self.assertRaises(exceptions.InputException):
      _result = self.servlet.ParsePersonData(mr, post_data)

  def testParsePersonData_NoDetails(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project)
    post_data = fake.PostData(role=['owner'])
    u, r, ac, n, _ = self.servlet.ParsePersonData(mr, post_data)
    self.assertEquals(111, u)
    self.assertEquals('owner', r)
    self.assertEquals([], ac)
    self.assertEquals('', n)

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=333',
        project=self.project)
    post_data = fake.PostData(role=['owner'])
    u, r, ac, n, _ = self.servlet.ParsePersonData(mr, post_data)
    self.assertEquals(333, u)

  def testParsePersonData(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project)
    post_data = fake.PostData(
        role=['owner'], extra_perms=['ViewQuota', 'EditIssue'])
    u, r, ac, n, _ = self.servlet.ParsePersonData(mr, post_data)
    self.assertEquals(111, u)
    self.assertEquals('owner', r)
    self.assertEquals(['ViewQuota', 'EditIssue'], ac)
    self.assertEquals('', n)

    post_data = fake.PostData({
        'role': ['owner'],
        'extra_perms': [' ', '  \t'],
        'notes': [''],
        })
    u, r, ac, n, ac_exclusion = self.servlet.ParsePersonData(mr, post_data)
    self.assertEquals(111, u)
    self.assertEquals('owner', r)
    self.assertEquals([], ac)
    self.assertEquals('', n)
    self.assertFalse(ac_exclusion)

    post_data = fake.PostData({
        'username': ['jrobbins'],
        'role': ['owner'],
        'extra_perms': ['_ViewQuota', '  __EditIssue'],
        'notes': [' Our local Python expert '],
        'ac_exclude': [123],
        })
    u, r, ac, n, ac_exclusion = self.servlet.ParsePersonData(mr, post_data)
    self.assertEquals(111, u)
    self.assertEquals('owner', r)
    self.assertEquals(['ViewQuota', 'EditIssue'], ac)
    self.assertEquals('Our local Python expert', n)
    self.assertTrue(ac_exclusion)

  def testCanEditMemberNotes(self):
    """Only owners can edit member notes."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    result = self.servlet.CanEditMemberNotes(mr, 222)
    self.assertFalse(result)

    mr.auth.user_id = 222
    result = self.servlet.CanEditMemberNotes(mr, 222)
    self.assertTrue(result)

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    result = self.servlet.CanEditMemberNotes(mr, 222)
    self.assertTrue(result)

  def testCanEditPerms(self):
    """Only owners can edit member perms."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    result = self.servlet.CanEditPerms(mr)
    self.assertFalse(result)

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    result = self.servlet.CanEditPerms(mr)
    self.assertTrue(result)

  def testCanRemoveRole(self):
    """Owners can remove members. Users could also remove themselves."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    result = self.servlet.CanRemoveRole(mr, 222)
    self.assertFalse(result)

    mr.auth.user_id = 111
    result = self.servlet.CanRemoveRole(mr, 111)
    self.assertTrue(result)

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/detail?u=111',
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    result = self.servlet.CanRemoveRole(mr, 222)
    self.assertTrue(result)
