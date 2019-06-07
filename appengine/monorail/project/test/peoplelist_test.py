# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for People List servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import authdata
from framework import permissions
from project import peoplelist
from proto import user_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class PeopleListTest(unittest.TestCase):
  """Tests for the PeopleList servlet."""

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    services.user.TestAddUser('jrobbins@gmail.com', 111)
    services.user.TestAddUser('jrobbins@jrobbins.org', 222)
    services.user.TestAddUser('jrobbins@chromium.org', 333)
    services.user.TestAddUser('imso31337@gmail.com', 999)
    self.project = services.project.TestAddProject('proj')
    self.project.owner_ids.extend([111])
    self.project.committer_ids.extend([222])
    self.project.contributor_ids.extend([333])
    self.servlet = peoplelist.PeopleList('req', 'res', services=services)

  def VerifyAccess(self, exception_expected):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/list',
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.servlet.AssertBasePermission(mr)
    # Owner never raises PermissionException.

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/list',
        project=self.project,
        perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    self.servlet.AssertBasePermission(mr)
    # Committer never raises PermissionException.

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/list',
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

  def testAssertBasePermission_HideMembers(self):
    self.project.only_owners_see_contributors = True
    self.VerifyAccess(True)

  def testGatherPageData(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/list',
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    mr.auth = authdata.AuthData()
    page_data = self.servlet.GatherPageData(mr)

    self.assertEqual(1, page_data['total_num_owners'])
    # TODO(jrobbins): fill in tests for all other aspects.

  def testProcessFormData_Permission(self):
    """Only owners could add/remove members."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/list',
        project=self.project,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    self.assertRaises(permissions.PermissionException,
                      self.servlet.ProcessFormData, mr, {})

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/list',
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.servlet.ProcessFormData(mr, {})

  def testGatherHelpData_Anon(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/list',
        project=self.project)
    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(
        {'account_cue': None, 'cue': None},
        help_data)

  def testGatherHelpData_Nonmember(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/list',
        project=self.project)
    mr.auth.user_id = 999
    mr.auth.effective_ids = {999}
    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(
        {'account_cue': None, 'cue': 'how_to_join_project'},
        help_data)

    self.servlet.services.user.SetUserPrefs(
        'cnxn', 999,
        [user_pb2.UserPrefValue(name='how_to_join_project', value='true')])
    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(
        {'account_cue': None, 'cue': None},
        help_data)

  def testGatherHelpData_Member(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/people/list',
        project=self.project)
    mr.auth.user_id = 111
    mr.auth.effective_ids = {111}
    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(
        {'account_cue': None, 'cue': None},
        help_data)
