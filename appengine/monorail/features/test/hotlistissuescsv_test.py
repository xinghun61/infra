# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for issuelistcsv module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from google.appengine.ext import testbed

import webapp2

from framework import permissions
from framework import sorting
from framework import xsrf
from services import service_manager
from testing import fake
from testing import testing_helpers
from features import hotlistissuescsv


class HotlistIssuesCsvTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.services = service_manager.Services(
        issue_star=fake.IssueStarService(),
        config=fake.ConfigService(),
        user=fake.UserService(),
        issue=fake.IssueService(),
        project=fake.ProjectService(),
        cache_manager=fake.CacheManager(),
        features=fake.FeaturesService())
    self.servlet = hotlistissuescsv.HotlistIssuesCsv(
        'req', webapp2.Response(), services=self.services)
    self.user1 = self.services.user.TestAddUser('testuser@gmail.com', 111)
    self.user2 = self.services.user.TestAddUser('testuser2@gmail.com', 222)
    self.services.project.TestAddProject('project-name', project_id=1)
    self.issue1 = fake.MakeTestIssue(
        1, 1, 'issue_summary', 'New', 111, project_name='project-name')
    self.services.issue.TestAddIssue(self.issue1)
    self.issues = [self.issue1]
    self.hotlist_item_fields = [
        (issue.issue_id, rank, 111, 1205079300, '') for
        rank, issue in enumerate(self.issues)]
    self.hotlist = self.services.features.TestAddHotlist(
        'MyHotlist', hotlist_id=123, owner_ids=[222], editor_ids=[111],
        hotlist_item_fields=self.hotlist_item_fields)
    self._MakeMR('/u/222/hotlists/MyHotlist')
    sorting.InitializeArtValues(self.services)

  def _MakeMR(self, path):
    self.mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.hotlist, path=path, services=self.services)
    self.mr.hotlist_id = self.hotlist.hotlist_id
    self.mr.hotlist = self.hotlist

  def testGatherPageData_AnonUsers(self):
    """Anonymous users cannot download the issue list."""
    self.mr.auth.user_id = 0
    self.assertRaises(permissions.PermissionException,
                      self.servlet.GatherPageData, self.mr)

  def testGatherPageData_NoXSRF(self):
    """Users need a valid XSRF token to download the issue list."""
    # Note no token query-string parameter is set.
    self.mr.auth.user_id = self.user2.user_id
    self.assertRaises(xsrf.TokenIncorrect,
                      self.servlet.GatherPageData, self.mr)

  def testGatherPageData_BadXSRF(self):
    """Users need a valid XSRF token to download the issue list."""
    for path in ('/u/222/hotlists/MyHotlist',
                 '/u/testuser2@gmail.com/hotlists/MyHotlist'):
      token = 'bad'
      self._MakeMR(path + '?token=%s' % token)
      self.mr.auth.user_id = self.user2.user_id
      self.assertRaises(xsrf.TokenIncorrect,
                        self.servlet.GatherPageData, self.mr)

  def testGatherPageData_Normal(self):
    """Users can get the hotlist issue list."""
    for path in ('/u/222/hotlists/MyHotlist',
                 '/u/testuser2@gmail.com/hotlists/MyHotlist'):
      form_token_path = self.servlet._FormHandlerURL(path)
      token = xsrf.GenerateToken(self.user1.user_id, form_token_path)
      self._MakeMR(path + '?token=%s' % token)
      self.mr.auth.email = self.user1.email
      self.mr.auth.user_id = self.user1.user_id
      self.servlet.GatherPageData(self.mr)
