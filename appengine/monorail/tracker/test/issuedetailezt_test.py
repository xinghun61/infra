# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.issuedetailezt."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import mock
import mox
import time
import unittest

import settings
from businesslogic import work_env
from proto import features_pb2
from features import hotlist_views
from features import send_notifications
from framework import authdata
from framework import exceptions
from framework import framework_views
from framework import framework_helpers
from framework import urls
from framework import permissions
from framework import profiler
from framework import sorting
from framework import template_helpers
from proto import project_pb2
from proto import tracker_pb2
from proto import user_pb2
from services import service_manager
from services import issue_svc
from services import tracker_fulltext
from testing import fake
from testing import testing_helpers
from tracker import issuedetailezt
from tracker import tracker_constants
from tracker import tracker_helpers


class GetAdjacentIssueTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService(),
        issue_star=fake.IssueStarService(),
        spam=fake.SpamService())
    self.services.project.TestAddProject('proj', project_id=789)
    self.mr = testing_helpers.MakeMonorailRequest()
    self.mr.auth.user_id = 111
    self.mr.auth.effective_ids = {111}
    self.mr.me_user_id = 111
    self.work_env = work_env.WorkEnv(
      self.mr, self.services, 'Testing phase')

  def testGetAdjacentIssue_PrevIssue(self):
    cur_issue = fake.MakeTestIssue(789, 2, 'sum', 'New', 111, issue_id=78902)
    next_issue = fake.MakeTestIssue(789, 3, 'sum', 'New', 111, issue_id=78903)
    prev_issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(cur_issue)
    self.services.issue.TestAddIssue(next_issue)
    self.services.issue.TestAddIssue(prev_issue)

    with self.work_env as we:
      we.FindIssuePositionInSearch = mock.Mock(
          return_value=[78901, 1, 78903, 3])

      actual_issue = issuedetailezt.GetAdjacentIssue(we, cur_issue)
      self.assertEqual(prev_issue, actual_issue)
      we.FindIssuePositionInSearch.assert_called_once_with(cur_issue)

  def testGetAdjacentIssue_NextIssue(self):
    cur_issue = fake.MakeTestIssue(789, 2, 'sum', 'New', 111, issue_id=78902)
    next_issue = fake.MakeTestIssue(789, 3, 'sum', 'New', 111, issue_id=78903)
    prev_issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(cur_issue)
    self.services.issue.TestAddIssue(next_issue)
    self.services.issue.TestAddIssue(prev_issue)

    with self.work_env as we:
      we.FindIssuePositionInSearch = mock.Mock(
          return_value=[78901, 1, 78903, 3])

      actual_issue = issuedetailezt.GetAdjacentIssue(
          we, cur_issue, next_issue=True)
      self.assertEqual(next_issue, actual_issue)
      we.FindIssuePositionInSearch.assert_called_once_with(cur_issue)

  def testGetAdjacentIssue_NotFound(self):
    cur_issue = fake.MakeTestIssue(789, 2, 'sum', 'New', 111, issue_id=78902)
    prev_issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(cur_issue)
    self.services.issue.TestAddIssue(prev_issue)

    with self.work_env as we:
      we.FindIssuePositionInSearch = mock.Mock(
          return_value=[78901, 1, 78903, 3])

      with self.assertRaises(exceptions.NoSuchIssueException):
        issuedetailezt.GetAdjacentIssue(we, cur_issue, next_issue=True)
      we.FindIssuePositionInSearch.assert_called_once_with(cur_issue)


class FlipperRedirectTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        features=fake.FeaturesService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService())
    self.project = self.services.project.TestAddProject(
      'proj', project_id=987, committer_ids=[111])
    self.next_servlet = issuedetailezt.FlipperNext(
        'req', 'res', services=self.services)
    self.prev_servlet = issuedetailezt.FlipperPrev(
        'req', 'res', services=self.services)
    self.list_servlet = issuedetailezt.FlipperList(
        'req', 'res', services=self.services)
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    mr.local_id = 123
    mr.me_user_id = 111

    self.next_servlet.mr = mr
    self.prev_servlet.mr = mr
    self.list_servlet.mr = mr

    self.fake_issue_1 = fake.MakeTestIssue(987, 123, 'summary', 'New', 111,
        project_name='rutabaga')
    self.services.issue.TestAddIssue(self.fake_issue_1)
    self.fake_issue_2 = fake.MakeTestIssue(987, 456, 'summary', 'New', 111,
        project_name='rutabaga')
    self.services.issue.TestAddIssue(self.fake_issue_2)
    self.fake_issue_3 = fake.MakeTestIssue(987, 789, 'summary', 'New', 111,
        project_name='potato')
    self.services.issue.TestAddIssue(self.fake_issue_3)

    self.next_servlet.redirect = mock.Mock()
    self.prev_servlet.redirect = mock.Mock()
    self.list_servlet.redirect = mock.Mock()

  @mock.patch('tracker.issuedetailezt.GetAdjacentIssue')
  def testFlipperNext(self, patchGetAdjacentIssue):
    patchGetAdjacentIssue.return_value = self.fake_issue_2
    self.next_servlet.mr.GetIntParam = mock.Mock(return_value=None)

    self.next_servlet.get(project_name='proj', viewed_username=None)
    self.next_servlet.mr.GetIntParam.assert_called_once_with('hotlist_id')
    patchGetAdjacentIssue.assert_called_once()
    self.next_servlet.redirect.assert_called_once_with(
      '/p/rutabaga/issues/detail?id=456')

  @mock.patch('tracker.issuedetailezt.GetAdjacentIssue')
  def testFlipperNext_Hotlist(self, patchGetAdjacentIssue):
    patchGetAdjacentIssue.return_value = self.fake_issue_3
    self.next_servlet.mr.GetIntParam = mock.Mock(return_value=123)
    # TODO(jeffcarp): Mock hotlist_id param on path here.

    self.next_servlet.get(project_name='proj', viewed_username=None)
    self.next_servlet.mr.GetIntParam.assert_called_with('hotlist_id')
    self.next_servlet.redirect.assert_called_once_with(
      '/p/potato/issues/detail?id=789')

  @mock.patch('tracker.issuedetailezt.GetAdjacentIssue')
  def testFlipperPrev(self, patchGetAdjacentIssue):
    patchGetAdjacentIssue.return_value = self.fake_issue_2
    self.next_servlet.mr.GetIntParam = mock.Mock(return_value=None)

    self.prev_servlet.get(project_name='proj', viewed_username=None)
    self.prev_servlet.mr.GetIntParam.assert_called_with('hotlist_id')
    patchGetAdjacentIssue.assert_called_once()
    self.prev_servlet.redirect.assert_called_once_with(
      '/p/rutabaga/issues/detail?id=456')

  @mock.patch('tracker.issuedetailezt.GetAdjacentIssue')
  def testFlipperPrev_Hotlist(self, patchGetAdjacentIssue):
    patchGetAdjacentIssue.return_value = self.fake_issue_3
    self.prev_servlet.mr.GetIntParam = mock.Mock(return_value=123)
    # TODO(jeffcarp): Mock hotlist_id param on path here.

    self.prev_servlet.get(project_name='proj', viewed_username=None)
    self.prev_servlet.mr.GetIntParam.assert_called_with('hotlist_id')
    self.prev_servlet.redirect.assert_called_once_with(
      '/p/potato/issues/detail?id=789')

  @mock.patch('tracker.issuedetailezt._ComputeBackToListURL')
  def testFlipperList(self, patch_ComputeBackToListURL):
    patch_ComputeBackToListURL.return_value = '/p/test/issues/list'
    self.list_servlet.mr.GetIntParam = mock.Mock(return_value=None)

    self.list_servlet.get()

    self.list_servlet.mr.GetIntParam.assert_called_with('hotlist_id')
    patch_ComputeBackToListURL.assert_called_once()
    self.list_servlet.redirect.assert_called_once_with(
      '/p/test/issues/list')

  @mock.patch('tracker.issuedetailezt._ComputeBackToListURL')
  def testFlipperList_Hotlist(self, patch_ComputeBackToListURL):
    patch_ComputeBackToListURL.return_value = '/p/test/issues/list'
    self.list_servlet.mr.GetIntParam = mock.Mock(return_value=123)

    self.list_servlet.get()

    self.list_servlet.mr.GetIntParam.assert_called_with('hotlist_id')
    self.list_servlet.redirect.assert_called_once_with(
      '/p/test/issues/list')


class ShouldShowFlipperTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'

  def VerifyShouldShowFlipper(
      self, expected, query, sort_spec, can, create_issues=0):
    """Instantiate a _Flipper and check if makes a pipeline or not."""
    services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        project=fake.ProjectService(),
        user=fake.UserService())
    project = services.project.TestAddProject(
      'proj', project_id=987, committer_ids=[111])
    mr = testing_helpers.MakeMonorailRequest(project=project)
    mr.query = query
    mr.sort_spec = sort_spec
    mr.can = can
    mr.project_name = project.project_name
    mr.project = project

    for idx in range(create_issues):
      _local_id, _ = services.issue.CreateIssue(
          self.cnxn, services, project.project_id,
          'summary_%d' % idx, 'status', 111, [], [], [], [], 111,
          'description_%d' % idx)

    self.assertEqual(expected, issuedetailezt._ShouldShowFlipper(mr, services))

  def testShouldShowFlipper_RegularSizedProject(self):
    # If the user is looking for a specific issue, no flipper.
    self.VerifyShouldShowFlipper(
        False, '123', '', tracker_constants.OPEN_ISSUES_CAN)
    self.VerifyShouldShowFlipper(False, '123', '', 5)
    self.VerifyShouldShowFlipper(
        False, '123', 'priority', tracker_constants.OPEN_ISSUES_CAN)

    # If the user did a search or sort or all in a small can, show flipper.
    self.VerifyShouldShowFlipper(
        True, 'memory leak', '', tracker_constants.OPEN_ISSUES_CAN)
    self.VerifyShouldShowFlipper(
        True, 'id=1,2,3', '', tracker_constants.OPEN_ISSUES_CAN)
    # Any can other than 1 or 2 is doing a query and so it should have a
    # failry narrow result set size.  5 is issues starred by me.
    self.VerifyShouldShowFlipper(True, '', '', 5)
    self.VerifyShouldShowFlipper(
        True, '', 'status', tracker_constants.OPEN_ISSUES_CAN)

    # In a project without a huge number of issues, still show the flipper even
    # if there was no specific query.
    self.VerifyShouldShowFlipper(
        True, '', '', tracker_constants.OPEN_ISSUES_CAN)

  def testShouldShowFlipper_LargeSizedProject(self):
    settings.threshold_to_suppress_prev_next = 1

    # In a project that has tons of issues, save time by not showing the
    # flipper unless there was a specific query, sort, or can.
    self.VerifyShouldShowFlipper(
        False, '', '', tracker_constants.ALL_ISSUES_CAN, create_issues=3)
    self.VerifyShouldShowFlipper(
        False, '', '', tracker_constants.OPEN_ISSUES_CAN, create_issues=3)
