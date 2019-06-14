# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for servlet base class helper functions."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

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
    timestamp = [2019, 6, 13, 18, 30]

    banner_time = servlet_helpers.GetBannerTime(timestamp)
    self.assertEqual(1560450600, banner_time)


class AssertBasePermissionTest(unittest.TestCase):

  def testAccessGranted(self):
    _, mr = testing_helpers.GetRequestObjects(path='/hosting')
    # No exceptions should be raised.
    servlet_helpers.AssertBasePermission(mr)

    mr.auth.user_id = 123
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

  def testPlusAddressAccount(self):
    _, mr = testing_helpers.GetRequestObjects(path='/hosting')
    mr.auth.user_pb.email = 'mailinglist+spammer@chromium.org'
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
    self.assertEqual('/p/proj/issues/entry', url)

  def testComputeIssueEntryURL_Customized(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/detail?id=123&q=term',
        project=self.project)
    mr.auth.user_id = 111
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
    self.project.owner_ids = [111]
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
        user_info={'effective_ids': {111}})
    self.config.member_default_query = 'owner:me'

    url = servlet_helpers.IssueListURL(mr, self.config)
    self.assertEqual('/p/proj/issues/list?q=owner%3Ame', url)

  def testIssueListURL_Customized_RetainQS(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues', project=self.project,
        user_info={'effective_ids': {111}})
    self.config.member_default_query = 'owner:me'

    url = servlet_helpers.IssueListURL(mr, self.config, query_string='')
    self.assertEqual('/p/proj/issues/list?q=owner%3Ame', url)

    url = servlet_helpers.IssueListURL(mr, self.config, query_string='q=Pri=1')
    self.assertEqual('/p/proj/issues/list?q=Pri=1', url)
