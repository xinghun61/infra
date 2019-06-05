# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.issuepeek."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
import mock

from google.appengine.ext import testbed

from framework import framework_constants
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
        issue_star=fake.IssueStarService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        features=fake.FeaturesService(),
        spam=fake.SpamService())
    self.services.user.TestAddUser('suer@example.com', 111)
    self.proj = self.services.project.TestAddProject('proj', project_id=789)
    self.cnxn = 'fake cnxn'
    self.servlet = issuepeek.IssuePeek(
        'req', 'res', services=self.services)
    self.local_id_1, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services,
        789, 'summary', 'status', 111, [], [], [], [], 111,
        'The screen is just dark when I press power on')

  def tearDown(self):
    self.testbed.deactivate()

  @mock.patch('framework.permissions.GetPermissions')
  def testGatherPageData_NoPermission(self, mock_getpermissions):
    """Permit users who can view issues."""
    # Empty permissionset does not have the VIEW permission.
    mr = testing_helpers.MakeMonorailRequest(project=self.proj)
    mock_getpermissions.return_value = permissions.EMPTY_PERMISSIONSET
    mr.local_id = self.local_id_1
    self.assertRaises(permissions.PermissionException,
                      self.servlet.GatherPageData, mr)

    # User permissionset has the VIEW permission.
    mock_getpermissions.return_value = permissions.USER_PERMISSIONSET
    self.servlet.GatherPageData(mr)

  def testPaginateComments_NotVisible(self):
    mr = testing_helpers.MakeMonorailRequest()
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'New', 111)
    issuecomment_list = [tracker_pb2.IssueComment()]

    # No comments yet.
    descriptions, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config, self.services)
    self.assertEqual([issuecomment_list[0]], descriptions)
    self.assertEqual(issuecomment_list[1:], visible_comments)
    self.assertFalse(pagination.visible)

    # 5 comments, none deleted.
    for _ in range(5):
      issuecomment_list.append(tracker_pb2.IssueComment())
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config, self.services)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[1:], visible_comments)
    self.assertFalse(pagination.visible)

    # 5 comments, 1 of them deleted.
    issuecomment_list[1].deleted_by = 123
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config, self.services)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[2:], visible_comments)
    self.assertFalse(pagination.visible)

  def testPaginateComments_Visible(self):
    mr = testing_helpers.MakeMonorailRequest()
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'New', 111)
    issuecomment_list = [tracker_pb2.IssueComment()]
    # full page of comments, none deleted.
    for _ in range(framework_constants.DEFAULT_COMMENTS_PER_PAGE):
      issuecomment_list.append(tracker_pb2.IssueComment())
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config, self.services)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[1:], visible_comments)
    self.assertFalse(pagination.visible)

    # One comment on second page, none deleted.
    issuecomment_list.append(tracker_pb2.IssueComment())
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config, self.services)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[2:], visible_comments)
    self.assertTrue(pagination.visible)
    self.assertEqual(2, pagination.last)
    self.assertEqual(framework_constants.DEFAULT_COMMENTS_PER_PAGE + 1,
        pagination.start)

    # One comment on second page, 1 of them deleted.
    issuecomment_list[1].deleted_by = 123
    description, visible_comments, pagination = issuepeek.PaginateComments(
        mr, issue, issuecomment_list, config, self.services)
    self.assertEqual([issuecomment_list[0]], description)
    self.assertEqual(issuecomment_list[2:], visible_comments)
    self.assertFalse(pagination.visible)
