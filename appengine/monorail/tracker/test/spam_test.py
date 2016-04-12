# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.spam."""

import unittest

from framework import permissions
from services import service_manager
from services import issue_svc
from testing import fake
from testing import testing_helpers
from tracker import spam


class FlagSpamFormTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
      config=fake.ConfigService(),
      issue=fake.IssueService(),
      user=fake.UserService(),
      project=fake.ProjectService(),
      spam=fake.SpamService()
    )
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.servlet = spam.FlagSpamForm(
        'req', 'res', services=self.services)

  def testProcessFormData_Permission(self):
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id,
        'summary_1', 'status', 111L, [], [], [], [], 111L, 'description_1')

    # test owner case.
    _, mr = testing_helpers.GetRequestObjects(
      project=self.project,
      perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    mr.local_id = local_id_1
    mr.auth_user_id = 222L
    post_data = {
      'id': local_id_1,
      'spam': 'true'
    }
    res = self.servlet.ProcessFormData(mr, post_data)
    self.assertEqual('http://127.0.0.1/p/None/issues/detail?id=1', res)

    # test member case.
    _, mr = testing_helpers.GetRequestObjects(
      project=self.project,
      perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    mr.local_id = local_id_1
    mr.auth_user_id = 222L
    post_data = {
      'id': local_id_1,
      'spam': 'true'
    }
    res = self.servlet.ProcessFormData(mr, post_data)
    self.assertEqual('http://127.0.0.1/p/None/issues/detail?id=1', res)

    # test non-member case.
    _, mr = testing_helpers.GetRequestObjects(
      project=self.project,
      perms=permissions.READ_ONLY_PERMISSIONSET)
    mr.local_id = local_id_1
    mr.auth_user_id = 222L
    post_data = {
      'id': local_id_1,
      'spam': 'true'
    }

    with self.assertRaises(permissions.PermissionException):
      res = self.servlet.ProcessFormData(mr, post_data)


  def testProcessFormData_Comment(self):
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id,
        'summary_1', 'status', 111L, [], [], [], [], 111L, 'description_1')

    # test owner case, non-existent comment.
    _, mr = testing_helpers.GetRequestObjects(
      project=self.project,
      perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    mr.local_id = local_id_1
    mr.auth_user_id = 222L
    post_data = {
      'id': local_id_1,
      'comment_id': 123,
      'spam': 'true'
    }
    with self.assertRaises(issue_svc.NoSuchCommentException):
      res = self.servlet.ProcessFormData(mr, post_data)

    comment = self.services.issue.CreateIssueComment(
      self.cnxn, self.project.project_id, local_id_1, 111L, "Test comment")

    _, mr = testing_helpers.GetRequestObjects(
      project=self.project,
      perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    mr.local_id = local_id_1
    mr.auth_user_id = 222L
    post_data = {
      'id': local_id_1,
      'comment_id': comment.id,
      'sequence_num': 2,
      'spam': 'true'
    }

    res = self.servlet.ProcessFormData(mr, post_data)
    self.assertEqual('http://127.0.0.1/p/None/issues/detail?id=1', res)
