# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the issueoriginal module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest

import webapp2

from framework import exceptions
from framework import framework_helpers
from framework import monorailrequest
from framework import permissions
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issueoriginal


STRIPPED_MSG = 'Are you sure that it is   plugged in?\n'
ORIG_MSG = ('Are you sure that it is   plugged in?\n'
            '\n'
            '> Issue 1 entered by user foo:\n'
            '> http://blah blah\n'
            '> The screen is just dark when I press power on\n')
XXX_GOOD_UNICODE_MSG = u'Thanks,\n\342\230\206*username*'.encode('utf-8')
GOOD_UNICODE_MSG = u'Thanks,\n XXX *username*'
XXX_BAD_UNICODE_MSG = ORIG_MSG + ('\xff' * 1000)
BAD_UNICODE_MSG = ORIG_MSG + 'XXX'
GMAIL_CRUFT_MSG = ORIG_MSG  # XXX .replace('   ', ' \xa0 ')


class IssueOriginalTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService())
    self.servlet = issueoriginal.IssueOriginal(
        'req', 'res', services=self.services)

    self.proj = self.services.project.TestAddProject('proj', project_id=789)
    summary = 'System wont boot'
    status = 'New'
    cnxn = 'fake connection'
    self.services.user.TestAddUser('commenter@example.com', 222)
    self.local_id_1, desc = self.services.issue.CreateIssue(
        cnxn, self.services,
        789, summary, status, 111, [], [], [], [], 111,
        'The screen is just dark when I press power on')
    comment_0 = tracker_pb2.IssueComment(
        issue_id=desc.issue_id, user_id=222, project_id=789,
        content=STRIPPED_MSG, inbound_message=ORIG_MSG)
    self.services.issue.InsertComment(cnxn, comment_0)
    comment_1 = tracker_pb2.IssueComment(
        issue_id=desc.issue_id, user_id=222, project_id=789,
        content=STRIPPED_MSG, inbound_message=BAD_UNICODE_MSG)
    self.services.issue.InsertComment(cnxn, comment_1)
    comment_2 = tracker_pb2.IssueComment(
        issue_id=desc.issue_id, user_id=222, project_id=789,
        content=STRIPPED_MSG, inbound_message=GMAIL_CRUFT_MSG)
    self.services.issue.InsertComment(cnxn, comment_2)
    comment_3 = tracker_pb2.IssueComment(
        issue_id=desc.issue_id, user_id=222, project_id=789,
        content=STRIPPED_MSG, inbound_message=GOOD_UNICODE_MSG)
    self.services.issue.InsertComment(cnxn, comment_3)
    self.issue_1 = self.services.issue.GetIssueByLocalID(
        cnxn, 789, self.local_id_1)
    self.comments = [comment_0, comment_1, comment_2, comment_3]

  @mock.patch('framework.permissions.GetPermissions')
  def testAssertBasePermission(self, mock_getpermissions):
    """Permit users who can view issue, view inbound message and delete."""
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=1&seq=1',
        project=self.proj)

    # Allow the user to view the issue itself.
    mock_getpermissions.return_value = (
        permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)

    # Someone without VIEW permission cannot view the inbound email.
    mr.perms = permissions.EMPTY_PERMISSIONSET
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # Contributors don't have VIEW_INBOUND_MESSAGES.
    mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # Committers do have VIEW_INBOUND_MESSAGES.
    mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(mr)

    # But, a committer cannot use that if they cannot view the issue.
    self.issue_1.labels.append('Restrict-View-Foo')
    mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # Project owners have VIEW_INBOUND_MESSAGES and bypass restrictions.
    mock_getpermissions.return_value = (
        permissions.OWNER_ACTIVE_PERMISSIONSET)
    mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(mr)

  def testGatherPageData_Normal(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=1&seq=1',
        project=self.proj)
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(1, page_data['local_id'])
    self.assertEqual(1, page_data['seq'])
    self.assertFalse(page_data['is_binary'])
    self.assertEqual(ORIG_MSG, page_data['message_body'])

  def testGatherPageData_GoodUnicode(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=1&seq=4',
        project=self.proj)
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(1, page_data['local_id'])
    self.assertEqual(4, page_data['seq'])
    self.assertEqual(GOOD_UNICODE_MSG, page_data['message_body'])
    self.assertFalse(page_data['is_binary'])

  def testGatherPageData_BadUnicode(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=1&seq=2',
        project=self.proj)
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(1, page_data['local_id'])
    self.assertEqual(2, page_data['seq'])
    # xxx: should be true if cruft was there.
    # self.assertTrue(page_data['is_binary'])

  def testGatherPageData_GmailCruft(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=1&seq=3',
        project=self.proj)
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(1, page_data['local_id'])
    self.assertEqual(3, page_data['seq'])
    self.assertFalse(page_data['is_binary'])
    self.assertEqual(ORIG_MSG, page_data['message_body'])

  def testGatherPageData_404(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original',
        project=self.proj)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.GatherPageData(mr)
    self.assertEquals(404, cm.exception.code)

    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=1&seq=999',
        project=self.proj)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.GatherPageData(mr)
    self.assertEquals(404, cm.exception.code)

    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=999&seq=1',
        project=self.proj)
    with self.assertRaises(exceptions.NoSuchIssueException) as cm:
      self.servlet.GatherPageData(mr)

  def testGetIssueAndComment_Normal(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=1&seq=1',
        project=self.proj)
    issue, comment = self.servlet._GetIssueAndComment(mr)
    self.assertEqual(self.issue_1, issue)
    self.assertEqual(self.comments[1].content, comment.content)

  def testGetIssueAndComment_NoSuchComment(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=1&seq=99',
        project=self.proj)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet._GetIssueAndComment(mr)
    self.assertEquals(404, cm.exception.code)

  def testGetIssueAndComment_Malformed(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original',
        project=self.proj)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet._GetIssueAndComment(mr)
    self.assertEquals(404, cm.exception.code)

    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?id=1',
        project=self.proj)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet._GetIssueAndComment(mr)
    self.assertEquals(404, cm.exception.code)

    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/original?seq=1',
        project=self.proj)
    with self.assertRaises(exceptions.NoSuchIssueException) as cm:
      self.servlet._GetIssueAndComment(mr)
