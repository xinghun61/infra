# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for servlet base class helper functions."""

import unittest

from google.appengine.ext import testbed


from framework import permissions
from framework import servlet_helpers
from proto import project_pb2
from proto import tracker_pb2
from testing import testing_helpers


class EztDataTest(unittest.TestCase):

  def testGetBannerTime(self):
    """Tests GetBannerTime method."""
    timestamp = ['2009', '3', '13', '21', '24', '5']

    banner_time = servlet_helpers.GetBannerTime(timestamp)

    # Ensure that the banner timestamp falls in a timestamp range to account for
    # the test being run in different timezones.
    # Using "Sun, 12 Mar 2009 00:00:00 GMT" and "Sun, 15 Mar 2009 00:00:00 GMT".
    self.assertTrue(1236816000000 <= banner_time.ts <= 1237075200000)
    self.assertEqual(2009, banner_time.year)
    self.assertEqual(3, banner_time.month)
    self.assertEqual(13, banner_time.day)
    self.assertEqual(21, banner_time.hour)
    self.assertEqual(24, banner_time.minute)
    self.assertEqual(5, banner_time.second)
    self.assertEqual('Friday', banner_time.weekday)
    self.assertEqual('09:24PM', banner_time.hour_min)


class AssertBasePermissionTest(unittest.TestCase):

  def testAccessGranted(self):
    _, mr = testing_helpers.GetRequestObjects(path='/hosting')
    # No exceptions should be raised.
    servlet_helpers.AssertBasePermission(mr)

    mr.auth.user_id = 123L
    # No exceptions should be raised.
    servlet_helpers.AssertBasePermission(mr)
    servlet_helpers.AssertBasePermissionForUser(
        mr.auth.user_pb, mr.auth.user_view)

  def testBanned(self):
    _, mr = testing_helpers.GetRequestObjects(path='/hosting')
    mr.auth.user_pb.banned = 'spammer'
    self.assertRaises(
        permissions.BannedUserException,
        servlet_helpers.AssertBasePermissionForUser,
        mr.auth.user_pb, mr.auth.user_view)
    self.assertRaises(
        permissions.BannedUserException,
        servlet_helpers.AssertBasePermission, mr)

  def testNoAccessToProject(self):
    project = project_pb2.Project()
    project.project_name = 'proj'
    project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    _, mr = testing_helpers.GetRequestObjects(path='/p/proj/', project=project)
    mr.perms = permissions.EMPTY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        servlet_helpers.AssertBasePermission, mr)


FORM_URL = 'http://example.com/issues/form.php'


class ComputeIssueEntryURLTest(unittest.TestCase):

  def setUp(self):
    self.project = project_pb2.Project()
    self.project.project_name = 'proj'
    self.config = tracker_pb2.ProjectIssueConfig()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def testComputeIssueEntryURL_Normal(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/detail?id=123&q=term',
        project=self.project)

    url = servlet_helpers.ComputeIssueEntryURL(mr, self.config)
    self.assertEqual('entry', url)

  def testComputeIssueEntryURL_Customized(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/detail?id=123&q=term',
        project=self.project)
    mr.auth.user_id = 111L
    self.config.custom_issue_entry_url = FORM_URL

    url = servlet_helpers.ComputeIssueEntryURL(mr, self.config)
    self.assertTrue(url.startswith(FORM_URL))
    self.assertIn('token=', url)
    self.assertIn('role=', url)
    self.assertIn('continue=', url)

class IssueListURLTest(unittest.TestCase):

  def setUp(self):
    self.project = project_pb2.Project()
    self.project.project_name = 'proj'
    self.project.owner_ids = [111L]
    self.config = tracker_pb2.ProjectIssueConfig()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def testIssueListURL_NotCustomized(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues', project=self.project)

    url = servlet_helpers.IssueListURL(mr, self.config)
    self.assertEqual('/p/proj/issues/list', url)

  def testIssueListURL_Customized_Nonmember(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues', project=self.project)
    self.config.member_default_query = 'owner:me'

    url = servlet_helpers.IssueListURL(mr, self.config)
    self.assertEqual('/p/proj/issues/list', url)

  def testIssueListURL_Customized_Member(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues', project=self.project,
        user_info={'effective_ids': {111L}})
    self.config.member_default_query = 'owner:me'

    url = servlet_helpers.IssueListURL(mr, self.config)
    self.assertEqual('/p/proj/issues/list?q=owner%3Ame', url)

  def testIssueListURL_Customized_RetainQS(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues', project=self.project,
        user_info={'effective_ids': {111L}})
    self.config.member_default_query = 'owner:me'

    url = servlet_helpers.IssueListURL(mr, self.config, query_string='')
    self.assertEqual('/p/proj/issues/list?q=owner%3Ame', url)

    url = servlet_helpers.IssueListURL(mr, self.config, query_string='q=Pri=1')
    self.assertEqual('/p/proj/issues/list?q=Pri=1', url)
