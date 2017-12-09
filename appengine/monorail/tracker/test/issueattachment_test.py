# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for monorail.tracker.issueattachment."""

import unittest

from google.appengine.api import images
from google.appengine.ext import testbed

import mox
import webapp2

from framework import permissions
from framework import servlet
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issueattachment

from third_party import cloudstorage


class IssueattachmentTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_app_identity_stub()
    self.testbed.init_urlfetch_stub()
    self.attachment_data = ""

    self._old_gcs_open = cloudstorage.open
    cloudstorage.open = fake.gcs_open

    services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService())
    self.project = services.project.TestAddProject('proj')
    self.servlet = issueattachment.AttachmentPage(
        'req', webapp2.Response(), services=services)
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'summary', 'New', 111L)
    services.issue.TestAddIssue(self.issue)
    self.comment = tracker_pb2.IssueComment(
        id=123, issue_id=self.issue.issue_id,
        project_id=self.project.project_id, user_id=111L,
        content='this is a comment')
    services.issue.TestAddComment(self.comment, self.issue.local_id)
    self.attachment = tracker_pb2.Attachment(
        attachment_id=54321, filename='hello.txt', filesize=23432,
        mimetype='text/plain', gcs_object_id='/pid/attachments/hello.txt')
    services.issue.TestAddAttachment(
        self.attachment, self.comment.id, self.issue.issue_id)

  def tearDown(self):
    self.testbed.deactivate()
    cloudstorage.open = self._old_gcs_open

  def testGatherPageData_NotFound(self):
    aid = 12345
    # But, no such attachment is in the database.
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachment?aid=%s' % aid,
        perms=permissions.EMPTY_PERMISSIONSET)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.GatherPageData(mr)
    self.assertEquals(404, cm.exception.code)

  # TODO(jrobbins): test cases for missing comment and missing issue.

  def testGatherPageData_PermissionDenied(self):
    aid = self.attachment.attachment_id
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachment?aid=%s' % aid,
        perms=permissions.EMPTY_PERMISSIONSET)  # not even VIEW
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.GatherPageData, mr)

    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachment?aid=%s' % aid,
        perms=permissions.READ_ONLY_PERMISSIONSET)  # includes VIEW

    # issue is now deleted
    self.issue.deleted = True
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.GatherPageData, mr)
    self.issue.deleted = False

    # issue is now restricted
    self.issue.labels.extend(['Restrict-View-PermYouLack'])
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.GatherPageData, mr)

  def testGatherPageData_Download(self):
    aid = self.attachment.attachment_id
    self.mox.StubOutWithMock(self.servlet, 'redirect')
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachment?aid=%s' % aid,
        perms=permissions.READ_ONLY_PERMISSIONSET)  # includes VIEW
    self.servlet.redirect(mox.StrContains(self.attachment.filename), abort=True)
    self.mox.ReplayAll()
    self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()

  def testGatherPageData_DownloadBadFilename(self):
    aid = self.attachment.attachment_id
    self.attachment.filename = '<script>alert("xsrf")</script>.txt';
    self.mox.StubOutWithMock(self.servlet, 'redirect')
    _request, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        path='/p/proj/issues/attachment?aid=%s' % aid,
        perms=permissions.READ_ONLY_PERMISSIONSET)  # includes VIEW
    self.servlet.redirect(mox.And(
        mox.Not(mox.StrContains(self.attachment.filename)),
        mox.StrContains('attachment-%d.dat' % aid)), abort=True)
    self.mox.ReplayAll()
    self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()
