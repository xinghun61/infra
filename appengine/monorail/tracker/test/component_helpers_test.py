# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the component_helpers module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import tracker_pb2
from services import service_manager
from testing import fake
from tracker import component_helpers
from tracker import tracker_bizobj


class ComponentHelpersTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.cd1 = tracker_bizobj.MakeComponentDef(
        1, 789, 'FrontEnd', 'doc', False, [], [111], 0, 0)
    self.cd2 = tracker_bizobj.MakeComponentDef(
        2, 789, 'FrontEnd>Splash', 'doc', False, [], [222], 0, 0)
    self.cd3 = tracker_bizobj.MakeComponentDef(
        3, 789, 'BackEnd', 'doc', True, [], [111, 333], 0, 0)
    self.config.component_defs = [self.cd1, self.cd2, self.cd3]
    self.services = service_manager.Services(
        user=fake.UserService(),
        config=fake.ConfigService())
    self.services.user.TestAddUser('a@example.com', 111)
    self.services.user.TestAddUser('b@example.com', 222)
    self.services.user.TestAddUser('c@example.com', 333)
    self.mr = fake.MonorailRequest(self.services)
    self.mr.cnxn = fake.MonorailConnection()

  def testParseComponentRequest_Empty(self):
    post_data = fake.PostData(admins=[''], cc=[''], labels=[''])
    parsed = component_helpers.ParseComponentRequest(
        self.mr, post_data, self.services)
    self.assertEqual('', parsed.leaf_name)
    self.assertEqual('', parsed.docstring)
    self.assertEqual([], parsed.admin_usernames)
    self.assertEqual([], parsed.cc_usernames)
    self.assertEqual([], parsed.admin_ids)
    self.assertEqual([], parsed.cc_ids)
    self.assertFalse(self.mr.errors.AnyErrors())

  def testParseComponentRequest_Normal(self):
    post_data = fake.PostData(
        leaf_name=['FrontEnd'],
        docstring=['The server-side app that serves pages'],
        deprecated=[False],
        admins=['a@example.com'],
        cc=['b@example.com, c@example.com'],
        labels=['Hot, Cold'])
    parsed = component_helpers.ParseComponentRequest(
        self.mr, post_data, self.services)
    self.assertEqual('FrontEnd', parsed.leaf_name)
    self.assertEqual('The server-side app that serves pages', parsed.docstring)
    self.assertEqual(['a@example.com'], parsed.admin_usernames)
    self.assertEqual(['b@example.com', 'c@example.com'], parsed.cc_usernames)
    self.assertEqual(['Hot', 'Cold'], parsed.label_strs)
    self.assertEqual([111], parsed.admin_ids)
    self.assertEqual([222, 333], parsed.cc_ids)
    self.assertEqual([0, 1], parsed.label_ids)
    self.assertFalse(self.mr.errors.AnyErrors())

  def testParseComponentRequest_InvalidUser(self):
    post_data = fake.PostData(
        leaf_name=['FrontEnd'],
        docstring=['The server-side app that serves pages'],
        deprecated=[False],
        admins=['a@example.com, invalid_user'],
        cc=['b@example.com, c@example.com'],
        labels=[''])
    parsed = component_helpers.ParseComponentRequest(
        self.mr, post_data, self.services)
    self.assertEqual('FrontEnd', parsed.leaf_name)
    self.assertEqual('The server-side app that serves pages', parsed.docstring)
    self.assertEqual(['a@example.com', 'invalid_user'], parsed.admin_usernames)
    self.assertEqual(['b@example.com', 'c@example.com'], parsed.cc_usernames)
    self.assertEqual([111], parsed.admin_ids)
    self.assertEqual([222, 333], parsed.cc_ids)
    self.assertTrue(self.mr.errors.AnyErrors())
    self.assertEqual('invalid_user unrecognized', self.mr.errors.member_admins)

  def testGetComponentCcIDs(self):
    issue = tracker_pb2.Issue()
    issues_components_cc_ids = component_helpers.GetComponentCcIDs(
        issue, self.config)
    self.assertEqual(set(), issues_components_cc_ids)

    issue.component_ids = [1, 2]
    issues_components_cc_ids = component_helpers.GetComponentCcIDs(
        issue, self.config)
    self.assertEqual({111, 222}, issues_components_cc_ids)

  def testGetCcIDsForComponentAndAncestors(self):
    components_cc_ids = component_helpers.GetCcIDsForComponentAndAncestors(
        self.config, self.cd1)
    self.assertEqual({111}, components_cc_ids)

    components_cc_ids = component_helpers.GetCcIDsForComponentAndAncestors(
        self.config, self.cd2)
    self.assertEqual({111, 222}, components_cc_ids)

    components_cc_ids = component_helpers.GetCcIDsForComponentAndAncestors(
        self.config, self.cd3)
    self.assertEqual({111, 333}, components_cc_ids)
