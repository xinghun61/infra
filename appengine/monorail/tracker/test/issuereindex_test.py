# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.issuereindex."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import mox

import settings
from framework import permissions
from framework import template_helpers
from services import service_manager
from services import tracker_fulltext
from testing import fake
from testing import testing_helpers
from tracker import issuereindex


class IssueReindexTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testAssertBasePermission_NoAccess(self):
    # Non-members and contributors do not have permission to view this page.
    for permission in (permissions.USER_PERMISSIONSET,
                       permissions.COMMITTER_ACTIVE_PERMISSIONSET):
      request, mr = testing_helpers.GetRequestObjects(
          project=self.project, perms=permission)
      servlet = issuereindex.IssueReindex(
          request, 'res', services=self.services)
    with self.assertRaises(permissions.PermissionException) as cm:
      servlet.AssertBasePermission(mr)
    self.assertEqual('You are not allowed to administer this project',
                     cm.exception.message)

  def testAssertBasePermission_WithAccess(self):
    # Owners and admins have permission to view this page.
    for permission in (permissions.OWNER_ACTIVE_PERMISSIONSET,
                       permissions.ADMIN_PERMISSIONSET):
      request, mr = testing_helpers.GetRequestObjects(
          project=self.project, perms=permission)
      servlet = issuereindex.IssueReindex(
          request, 'res', services=self.services)
      servlet.AssertBasePermission(mr)

  def testGatherPageData(self):
    servlet = issuereindex.IssueReindex('req', 'res', services=self.services)

    mr = testing_helpers.MakeMonorailRequest()
    mr.auto_submit = True
    ret = servlet.GatherPageData(mr)

    self.assertTrue(ret['auto_submit'])
    self.assertIsNone(ret['issue_tab_mode'])
    self.assertTrue(ret['page_perms'].CreateIssue)

  def _callProcessFormData(self, post_data, index_issue_1=True):
    servlet = issuereindex.IssueReindex('req', 'res', services=self.services)

    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    mr.cnxn = self.cnxn

    issue1 = fake.MakeTestIssue(
        project_id=self.project.project_id, local_id=1, summary='sum',
        status='New', owner_id=111)
    issue1.project_name = self.project.project_name
    self.services.issue.TestAddIssue(issue1)

    self.mox.StubOutWithMock(tracker_fulltext, 'IndexIssues')
    if index_issue_1:
      tracker_fulltext.IndexIssues(
          self.cnxn, [issue1], self.services.user, self.services.issue,
          self.services.config)

    self.mox.ReplayAll()

    ret = servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    return ret

  def testProcessFormData_NormalInputs(self):
    post_data = {'start': 1, 'num': 5}
    ret = self._callProcessFormData(post_data)
    self.assertEquals(
        '/p/None/issues/reindex?start=6&auto_submit=False&num=5', ret)

  def testProcessFormData_LargeInputs(self):
    post_data = {'start': 0, 'num': 10000000}
    ret = self._callProcessFormData(post_data)
    self.assertEquals(
        '/p/None/issues/reindex?start=%s&auto_submit=False&num=%s' % (
            settings.max_artifact_search_results_per_page,
            settings.max_artifact_search_results_per_page),
        ret)

  def testProcessFormData_WithAutoSubmit(self):
    post_data = {'start': 1, 'num': 5, 'auto_submit': 1}
    ret = self._callProcessFormData(post_data)
    self.assertEquals(
        '/p/None/issues/reindex?start=6&auto_submit=True&num=5', ret)

  def testProcessFormData_WithAutoSubmitButNoMoreIssues(self):
    """This project has no issues 6-10, so stop autosubmitting."""
    post_data = {'start': 6, 'num': 5, 'auto_submit': 1}
    ret = self._callProcessFormData(post_data, index_issue_1=False)
    self.assertEquals(
        '/p/None/issues/reindex?start=11&auto_submit=False&num=5', ret)
