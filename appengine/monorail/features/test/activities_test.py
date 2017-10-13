# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.feature.activities."""

import unittest

import mox

from features import activities
from framework import framework_views
from framework import profiler
from proto import tracker_pb2
from proto import user_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class ActivitiesTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService(),
    )

    self.project_name = 'proj'
    self.project_id = 987
    self.project = self.services.project.TestAddProject(
        self.project_name, project_id=self.project_id,
        process_inbound_email=True)

    self.issue_id = 11
    self.issue_local_id = 100
    self.issue = tracker_pb2.Issue()
    self.issue.issue_id = self.issue_id
    self.issue.project_id = self.project_id
    self.issue.local_id = self.issue_local_id
    self.services.issue.TestAddIssue(self.issue)

    self.comment_id = 123
    self.comment_timestamp = 120
    self.user_id = 2
    self.mr_after = 1234

    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testActivities_NoUpdates(self):
    mr = testing_helpers.MakeMonorailRequest()
    updates_data = activities.GatherUpdatesData(
        self.services, mr, project_ids=[self.project_id],
        user_ids=None, ending=None, updates_page_url=None, autolink=None,
        highlight=None)

    self.assertIsNone(updates_data['pagination'])
    self.assertIsNone(updates_data['no_stars'])
    self.assertIsNone(updates_data['updates_data'])
    self.assertEqual('yes', updates_data['no_activities'])
    self.assertIsNone(updates_data['ending_type'])

  def createAndAssertUpdates(self, project_ids=None, user_ids=None,
                             ascending=True):
    user = user_pb2.MakeUser(self.user_id)
    comment_1 = tracker_pb2.IssueComment(
        id=self.comment_id, issue_id=self.issue_id,
        project_id=self.project_id, user_id=self.user_id,
        content='this is the 1st comment',
        timestamp=self.comment_timestamp)
    self.mox.StubOutWithMock(self.services.issue, 'GetComments')

    created_order = 'created'
    field = 'project_id' if project_ids else 'commenter_id'
    where_clauses = [('Issue.id = Comment.issue_id', [])]
    if project_ids:
      where_clauses.append(('Comment.project_id IN (%s)', project_ids))
    if user_ids:
      where_clauses.append(('Comment.commenter_id IN (%s)', user_ids))
    if ascending:
      where_clauses.append(('created > %s', [self.mr_after]))
    else:
      created_order += ' DESC'
    self.services.issue.GetComments(
        mox.IgnoreArg(), deleted_by=None,
        joins=[('Issue', [])], limit=activities.UPDATES_PER_PAGE + 1,
               order_by=[(created_order, [])],
        use_clause='USE INDEX (%s) USE INDEX FOR ORDER BY (%s)' % (field,
                                                                   field),
        where=where_clauses).AndReturn([comment_1])

    self.mox.StubOutWithMock(framework_views, 'MakeAllUserViews')
    framework_views.MakeAllUserViews(
        mox.IgnoreArg(), self.services.user, [self.user_id], []).AndReturn(
            {self.user_id: user})

    self.mox.ReplayAll()

    mr = testing_helpers.MakeMonorailRequest()
    if ascending:
      mr.after = self.mr_after

    updates_page_url='testing/testing'
    updates_data = activities.GatherUpdatesData(
        self.services, mr, project_ids=project_ids,
        user_ids=user_ids, ending=None, autolink=None,
        highlight='highlightme', updates_page_url=updates_page_url)
    self.mox.VerifyAll()

    if mr.after:
      pagination = updates_data['pagination']
      self.assertIsNone(pagination.last)
      self.assertEquals('%s?before=%d' % (updates_page_url.split('/')[-1],
                                          self.comment_timestamp),
                        pagination.next_url)
      self.assertEquals('%s?after=%d' % (updates_page_url.split('/')[-1],
                                         self.comment_timestamp),
                        pagination.prev_url)

    activity_view = updates_data['updates_data'].older[0]
    self.assertEqual(
        '<a class="ot-issue-link"\n \n '
        'href="/p//issues/detail?id=%s#c_ts%s"\n >'
        'issue %s</a>\n\n()\n\n\n\n\n \n commented on' % (
            self.issue_local_id, self.comment_timestamp, self.issue_local_id),
        activity_view.escaped_title)
    self.assertEqual(
        '<span class="ot-issue-comment">\n this is the 1st comment\n</span>',
        activity_view.escaped_body)
    self.assertEqual('highlightme', activity_view.highlight)
    self.assertEqual(self.project_name, activity_view.project_name)

  def testActivities_AscendingProjectUpdates(self):
    self.createAndAssertUpdates(project_ids=[self.project_id], ascending=True)

  def testActivities_DescendingProjectUpdates(self):
    self.createAndAssertUpdates(project_ids=[self.project_id], ascending=False)

  def testActivities_AscendingUserUpdates(self):
    self.createAndAssertUpdates(user_ids=[self.user_id], ascending=True)

  def testActivities_DescendingUserUpdates(self):
    self.createAndAssertUpdates(user_ids=[self.user_id], ascending=False)

  def testActivities_SpecifyProjectAndUser(self):
    self.createAndAssertUpdates(
        project_ids=[self.project_id], user_ids=[self.user_id], ascending=False)

