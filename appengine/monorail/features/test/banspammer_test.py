# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the ban spammer feature."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import os
import unittest
import webapp2

from features import banspammer
from framework import framework_views
from framework import permissions
from framework import urls
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers

from google.appengine.api import taskqueue
from google.appengine.ext import testbed

class BanSpammerTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.mr = testing_helpers.MakeMonorailRequest()
    self.services = service_manager.Services(
        issue=fake.IssueService(),
        project=fake.ProjectService(),
        spam=fake.SpamService(),
        user=fake.UserService())
    self.servlet = banspammer.BanSpammer('req', 'res', services=self.services)
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_taskqueue_stub()
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    self.taskqueue_stub._root_path = os.path.dirname(
        os.path.dirname(os.path.dirname( __file__ )))

  def tearDown(self):
    self.testbed.deactivate()

  def testProcessFormData_noPermission(self):
    self.servlet.services.user.TestAddUser('member', 222)
    self.servlet.services.user.TestAddUser('spammer@domain.com', 111)
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/spammer@domain.com/banSpammer.do',
        perms=permissions.GetPermissions(None, {}, None))
    mr.viewed_user_auth.user_view = framework_views.MakeUserView(mr.cnxn,
        self.servlet.services.user, 111)
    mr.auth.user_id = 222
    self.assertRaises(permissions.PermissionException,
        self.servlet.AssertBasePermission, mr)
    try:
      self.servlet.ProcessFormData(mr, {})
    except permissions.PermissionException:
      pass
    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.BAN_SPAMMER_TASK + '.do')
    self.assertEqual(0, len(tasks))

  def testProcessFormData_ok(self):
    self.servlet.services.user.TestAddUser('owner', 222)
    self.servlet.services.user.TestAddUser('spammer@domain.com', 111)
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/spammer@domain.com/banSpammer.do',
        perms=permissions.ADMIN_PERMISSIONSET)
    mr.viewed_user_auth.user_view = framework_views.MakeUserView(mr.cnxn,
        self.servlet.services.user, 111)
    self.servlet.ProcessFormData(mr, {})
    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.BAN_SPAMMER_TASK + '.do')
    self.assertEqual(1, len(tasks))


class BanSpammerTaskTest(unittest.TestCase):
  def setUp(self):
    self.services = service_manager.Services(
        issue=fake.IssueService(),
        spam=fake.SpamService())
    self.res = webapp2.Response()
    self.servlet = banspammer.BanSpammerTask('req', self.res,
        services=self.services)

  def testProcessFormData_okNoIssues(self):
    mr = testing_helpers.MakeMonorailRequest(
        path=urls.BAN_SPAMMER_TASK + '.do', method='POST',
        params={'spammer_id': 111, 'reporter_id': 222})

    self.servlet.HandleRequest(mr)
    self.assertEqual(self.res.body, json.dumps({'comments': 0, 'issues': 0}))

  def testProcessFormData_okSomeIssues(self):
    mr = testing_helpers.MakeMonorailRequest(
        path=urls.BAN_SPAMMER_TASK + '.do', method='POST',
        params={'spammer_id': 111, 'reporter_id': 222})

    for i in range(0, 10):
      issue = fake.MakeTestIssue(
          1, i, 'issue_summary', 'New', 111, project_name='project-name')
      self.servlet.services.issue.TestAddIssue(issue)

    self.servlet.HandleRequest(mr)
    self.assertEqual(self.res.body, json.dumps({'comments': 0, 'issues': 10}))

  def testProcessFormData_okSomeCommentsAndIssues(self):
    mr = testing_helpers.MakeMonorailRequest(
        path=urls.BAN_SPAMMER_TASK + '.do', method='POST',
        params={'spammer_id': 111, 'reporter_id': 222})

    for i in range(0, 12):
      issue = fake.MakeTestIssue(
          1, i, 'issue_summary', 'New', 111, project_name='project-name')
      self.servlet.services.issue.TestAddIssue(issue)

    for i in range(10, 20):
      issue = fake.MakeTestIssue(
          1, i, 'issue_summary', 'New', 222, project_name='project-name')
      self.servlet.services.issue.TestAddIssue(issue)
      for _ in range(0, 5):
        comment = tracker_pb2.IssueComment()
        comment.project_id = 1
        comment.user_id = 111
        comment.issue_id = issue.issue_id
        self.servlet.services.issue.TestAddComment(comment, issue.local_id)
    self.servlet.HandleRequest(mr)
    self.assertEqual(self.res.body, json.dumps({'comments': 50, 'issues': 10}))

