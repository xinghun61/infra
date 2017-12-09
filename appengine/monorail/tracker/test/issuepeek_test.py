# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.issuepeek."""

import unittest

from google.appengine.ext import testbed

from framework import permissions
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issuepeek
from tracker import tracker_bizobj


class IssuePeekTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        spam=fake.SpamService())
    self.proj = self.services.project.TestAddProject('proj', project_id=789)
    self.cnxn = 'fake cnxn'
    self.servlet = issuepeek.IssuePeek(
        'req', 'res', services=self.services)
    self.local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services,
        789, 'summary', 'status', 111L, [], [], [], [], 111L,
        'The screen is just dark when I press power on')

  def tearDown(self):
    self.testbed.deactivate()

  def testAssertBasePermission(self):
    """Permit users who can view issues."""
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.EMPTY_PERMISSIONSET)
    mr.local_id = self.local_id_1
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)
    mr.perms = permissions.USER_PERMISSIONSET
    self.servlet.AssertBasePermission(mr)

  def testPaginateComments_NotVisible(self):
    mr = testing_helpers.MakeMonorailRequest()
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'New', 111L)
    issuecomment_list = [tracker_pb2.IssueComment()]

    # No comments yet.
    descriptions, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config)
    self.assertEqual([issuecomment_list[0]], descriptions)
    self.assertEqual(issuecomment_list[1:], visible_comments)
    self.assertFalse(pagination.visible)

    # 5 comments, none deleted.
    for _ in range(5):
      issuecomment_list.append(tracker_pb2.IssueComment())
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[1:], visible_comments)
    self.assertFalse(pagination.visible)

    # 5 comments, 1 of them deleted.
    issuecomment_list[1].deleted_by = 123
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[2:], visible_comments)
    self.assertFalse(pagination.visible)

  def testPaginateComments_Visible(self):
    mr = testing_helpers.MakeMonorailRequest()
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'New', 111L)
    issuecomment_list = [tracker_pb2.IssueComment()]
    # 500 comments, none deleted.
    for _ in range(500):
      issuecomment_list.append(tracker_pb2.IssueComment())
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[1:], visible_comments)
    self.assertFalse(pagination.visible)

    # 501 comments, none deleted.
    issuecomment_list.append(tracker_pb2.IssueComment())
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[2:], visible_comments)
    self.assertTrue(pagination.visible)
    self.assertEqual(2, pagination.last)
    self.assertEqual(501, pagination.start)

    # 501 comments, 1 of them deleted.
    issuecomment_list[1].deleted_by = 123
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[2:], visible_comments)
    self.assertFalse(pagination.visible)
