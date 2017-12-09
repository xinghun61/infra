# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for issueattachmenttext."""

import logging
import unittest

from google.appengine.ext import testbed

from third_party import cloudstorage
from third_party import ezt

import webapp2

from framework import filecontent
from framework import permissions
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issueattachmenttext


class IssueAttachmentTextTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_app_identity_stub()

    services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService())
    self.project = services.project.TestAddProject('proj')
    self.servlet = issueattachmenttext.AttachmentText(
        'req', 'res', services=services)

    self.issue = tracker_pb2.Issue()
    self.issue.local_id = 1
    self.issue.issue_id = 1
    self.issue.summary = 'sum'
    self.issue.project_name = 'proj'
    self.issue.project_id = self.project.project_id
    services.issue.TestAddIssue(self.issue)

    self.comment0 = tracker_pb2.IssueComment()
    self.comment0.content = 'this is the description'
    self.comment1 = tracker_pb2.IssueComment()
    self.comment1.content = 'this is a comment'

    self.attach0 = tracker_pb2.Attachment(
        attachment_id=4567, filename='b.txt', mimetype='text/plain',
        gcs_object_id='/pid/attachments/abcd')
    self.comment0.attachments.append(self.attach0)

    self.attach1 = tracker_pb2.Attachment(
        attachment_id=1234, filename='a.txt', mimetype='text/plain',
        gcs_object_id='/pid/attachments/abcdefg')
    self.comment0.attachments.append(self.attach1)

    self.bin_attach = tracker_pb2.Attachment(
        attachment_id=2468, mimetype='application/octets',
        gcs_object_id='/pid/attachments/\0\0\0\0\0\1\2\3')
    self.comment1.attachments.append(self.bin_attach)

    self.comment0.project_id = self.project.project_id
    services.issue.TestAddComment(self.comment0, self.issue.local_id)
    self.comment1.project_id = self.project.project_id
    services.issue.TestAddComment(self.comment1, self.issue.local_id)
    services.issue.TestAddAttachment(
        self.attach0, self.comment0.id, self.issue.issue_id)
    services.issue.TestAddAttachment(
        self.attach1, self.comment1.id, self.issue.issue_id)
    # TODO(jrobbins): add tests for binary content
    self._old_gcs_open = cloudstorage.open
    cloudstorage.open = fake.gcs_open

  def tearDown(self):
    self.testbed.deactivate()
    cloudstorage.open = self._old_gcs_open

  def testGatherPageData_CommentDeleteed(self):
    """If the attachment's comment was deleted, give a 403."""
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/a/d.com/p/proj/issues/attachmentText?aid=1234',
        perms=permissions.READ_ONLY_PERMISSIONSET)
    self.servlet.GatherPageData(mr)  # OK
    self.comment1.deleted_by = 111L
    self.assertRaises(  # 403
        permissions.PermissionException,
        self.servlet.GatherPageData, mr)

  def testGatherPageData_IssueNotViewable(self):
    """If the attachment's issue is not viewable, give a 403."""
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachment?aid=1234',
        perms=permissions.EMPTY_PERMISSIONSET)  # No VIEW
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.GatherPageData, mr)

  def testGatherPageData_IssueDeleted(self):
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachment?aid=1234',
        perms=permissions.READ_ONLY_PERMISSIONSET)
    self.issue.deleted = True
    self.assertRaises(  # Issue was deleted
        permissions.PermissionException,
        self.servlet.GatherPageData, mr)

  def testGatherPageData_IssueRestricted(self):
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachment?aid=1234',
        perms=permissions.READ_ONLY_PERMISSIONSET)
    self.issue.labels.append('Restrict-View-Nobody')
    self.assertRaises(  # Issue is restricted
        permissions.PermissionException,
        self.servlet.GatherPageData, mr)

  def testGatherPageData_NoSuchAttachment(self):
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachmentText?aid=9999',
        perms=permissions.READ_ONLY_PERMISSIONSET)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.GatherPageData(mr)
    self.assertEquals(404, cm.exception.code)

  def testGatherPageData_AttachmentDeleted(self):
    """If the attachment was deleted, give a 404."""
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachmentText?aid=1234',
        perms=permissions.READ_ONLY_PERMISSIONSET)
    self.attach1.deleted = True
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.GatherPageData(mr)
    self.assertEquals(404, cm.exception.code)

  def testGatherPageData_Normal(self):
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachmentText?id=1&aid=1234',
        perms=permissions.READ_ONLY_PERMISSIONSET)
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(1, page_data['local_id'])
    self.assertEqual('a.txt', page_data['filename'])
    self.assertEqual('43 bytes', page_data['filesize'])
    self.assertEqual(ezt.boolean(False), page_data['should_prettify'])
    self.assertEqual(ezt.boolean(False), page_data['is_binary'])
    self.assertEqual(ezt.boolean(False), page_data['too_large'])

    file_lines = page_data['file_lines']
    self.assertEqual(1, len(file_lines))
    self.assertEqual(1, file_lines[0].num)
    self.assertEqual('/app_default_bucket/pid/attachments/abcdefg',
                     file_lines[0].line)

    self.assertEqual(None, page_data['code_reviews'])

  def testGatherPageData_HugeFile(self):
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachmentText?id=1&aid=1234',
        perms=permissions.READ_ONLY_PERMISSIONSET)

    def _MockDecodeFileContents(_content):
      return 'too large text', False, True

    orig_decode = filecontent.DecodeFileContents
    filecontent.DecodeFileContents = _MockDecodeFileContents
    try:
      page_data = self.servlet.GatherPageData(mr)
    finally:
      filecontent.DecodeFileContents = orig_decode

    filecontent.DecodeFileContents = orig_decode
    self.assertEqual(ezt.boolean(False), page_data['should_prettify'])
    self.assertEqual(ezt.boolean(False), page_data['is_binary'])
    self.assertEqual(ezt.boolean(True), page_data['too_large'])
