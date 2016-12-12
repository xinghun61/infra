# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for helpers module."""

import unittest

from features import hotlist_helpers
from framework import profiler
from framework import sorting
from services import service_manager
from testing import testing_helpers
from testing import fake
from proto import features_pb2
from proto import tracker_pb2


class CreateHotlistTableDataTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        issue=fake.IssueService(),
        features=fake.FeaturesService(),
        issue_star=fake.AbstractStarService(),
        config=fake.ConfigService(),
        project=fake.ProjectService(),
        user=fake.UserService(),
        cache_manager=fake.CacheManager())
    self.services.project.TestAddProject('ProjectName', project_id = 001)

    self.services.user.TestAddUser('annajowang@email.com', 111L)
    self.services.user.TestAddUser('claremont@email.com', 222L)
    issue1 = fake.MakeTestIssue(
        001, 1, 'issue_summary', 'New', 111L, project_name='ProjectName')
    self.services.issue.TestAddIssue(issue1)
    issue2 = fake.MakeTestIssue(
        001, 2, 'issue_summary2', 'New', 111L, project_name='ProjectName')
    self.services.issue.TestAddIssue(issue2)
    issue3 = fake.MakeTestIssue(
        001, 3, 'issue_summary3', 'New', 222L, project_name='ProjectName')
    self.services.issue.TestAddIssue(issue3)
    issues = [issue1, issue2, issue3]
    hotlist_issues = [
        (issue.issue_id, rank) for rank, issue in enumerate(issues)]

    self.iid_rank_pairs_list = [
        features_pb2.MakeHotlistIssue(
            issue_id, rank=rank) for (issue_id, rank) in hotlist_issues]
    self.test_hotlist = self.services.features.TestAddHotlist(
        'hotlist', hotlist_id=123,
        iid_rank_pairs=hotlist_issues)
    self.mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.test_hotlist)
    self.services.user.TestAddUser('annajo@email.com', 148L)
    self.mr.auth.effective_ids = {148L}
    self.mr.col_spec = 'ID Summary Modified'
    sorting.InitializeArtValues(self.services)

  def testCreateHotlistTableData(self):
    self.setUp()
    table_data, table_related_dict = hotlist_helpers.CreateHotlistTableData(
        self.mr, self.iid_rank_pairs_list, profiler.Profiler(), self.services)
    self.assertEqual(len(table_data), 3)
    start_index = 100001
    for row in table_data:
      self.assertEqual(row.project_name, 'ProjectName')
      self.assertEqual(row.issue_id, start_index)
      start_index += 1
    self.assertEqual(len(table_related_dict['column_values']), 3)

    # test none of the shown columns show up in unshown_columns
    self.assertTrue(
        set(self.mr.col_spec.split()).isdisjoint(
            table_related_dict['unshown_columns']))
    self.assertEqual(table_related_dict['is_cross_project'], False)
    self.assertEqual(len(table_related_dict['pagination'].visible_results), 3)


class GetAllProjectsOfIssuesTest(unittest.TestCase):

  issue_x_1 = tracker_pb2.Issue()
  issue_x_1.project_id = 789

  issue_x_2 = tracker_pb2.Issue()
  issue_x_2.project_id = 789

  issue_y_1 = tracker_pb2.Issue()
  issue_y_1.project_id = 678

  def testGetAllProjectsOfIssues_Normal(self):
    issues = [self.issue_x_1, self.issue_x_2]
    self.assertEqual(
        hotlist_helpers.GetAllProjectsOfIssues(issues),
        set([789]))
    issues = [self.issue_x_1, self.issue_x_2, self.issue_y_1]
    self.assertEqual(
        hotlist_helpers.GetAllProjectsOfIssues(issues),
        set([678, 789]))

  def testGetAllProjectsOfIssues_Empty(self):
    self.assertEqual(
        hotlist_helpers.GetAllProjectsOfIssues([]),
        set())


class HelpersUnitTest(unittest.TestCase):

  # TODO(jojwang): Write Tests for GetAllProjectsOfIssues,
  #  GetAllConfigsOfProjects, _MakeTableData
  def setUp(self):
    self.services = service_manager.Services(issue=fake.IssueService(),
                                        config=fake.ConfigService(),
                                        project=fake.ProjectService(),
                                        user=fake.UserService())
    self.project = self.services.project.TestAddProject(
        'ProjectName', project_id = 001, owner_ids=[111L])

    self.services.user.TestAddUser('annajowang@email.com', 111L)
    self.services.user.TestAddUser('claremont@email.com', 222L)
    self.issue1 = fake.MakeTestIssue(
        001, 1, 'issue_summary', 'New', 111L,
        project_name='ProjectName', labels='restrict-view-Googler')
    self.services.issue.TestAddIssue(self.issue1)
    self.issue3 = fake.MakeTestIssue(
        001, 3, 'issue_summary3', 'New', 222L, project_name='ProjectName')
    self.services.issue.TestAddIssue(self.issue3)
    self.issues = [self.issue1, self.issue3]
    self.mr = testing_helpers.MakeMonorailRequest()

  def testFilterIssues(self):
    test_allowed_issues = hotlist_helpers.FilterIssues(
        self.mr, self.issues, self.services)
    self.assertEqual(len(test_allowed_issues), 1)
    self.assertEqual(test_allowed_issues[0].local_id, 3)

  def testMembersWithoutGivenIDs(self):
    h = features_pb2.Hotlist()
    owners, editors, followers = hotlist_helpers.MembersWithoutGivenIDs(
        h, set())
    # Check lists are empty
    self.assertFalse(owners)
    self.assertFalse(editors)
    self.assertFalse(followers)

    h.owner_ids.extend([1, 2, 3])
    h.editor_ids.extend([4, 5, 6])
    h.follower_ids.extend([7, 8, 9])
    owners, editors, followers = hotlist_helpers.MembersWithoutGivenIDs(
        h, {10, 11, 12})
    self.assertEqual(h.owner_ids, owners)
    self.assertEqual(h.editor_ids, editors)
    self.assertEqual(h.follower_ids, followers)

    owners, editors, followers = hotlist_helpers.MembersWithoutGivenIDs(
        h, set())
    self.assertEqual(h.owner_ids, owners)
    self.assertEqual(h.editor_ids, editors)
    self.assertEqual(h.follower_ids, followers)

    owners, editors, followers = hotlist_helpers.MembersWithoutGivenIDs(
        h, {1, 4, 7})
    self.assertEqual([2, 3], owners)
    self.assertEqual([5, 6], editors)
    self.assertEqual([8, 9], followers)

  def testMembersWithGivenIDs(self):
    h = features_pb2.Hotlist()

    # empty GivenIDs give empty member lists from originally empty member lists
    owners, editors, followers = hotlist_helpers.MembersWithGivenIDs(
        h, set(), 'follower')
    self.assertFalse(owners)
    self.assertFalse(editors)
    self.assertFalse(followers)

    # empty GivenIDs return original non-empty member lists
    h.owner_ids.extend([1, 2, 3])
    h.editor_ids.extend([4, 5, 6])
    h.follower_ids.extend([7, 8, 9])
    owners, editors, followers = hotlist_helpers.MembersWithGivenIDs(
        h, set(), 'editor')
    self.assertEqual(owners, h.owner_ids)
    self.assertEqual(editors, h.editor_ids)
    self.assertEqual(followers, h.follower_ids)

    # non-member GivenIDs return updated member lists
    owners, editors, followers = hotlist_helpers.MembersWithGivenIDs(
        h, {10, 11, 12}, 'owner')
    self.assertEqual(owners, [1, 2, 3, 10, 11, 12])
    self.assertEqual(editors, [4, 5, 6])
    self.assertEqual(followers, [7, 8, 9])

    # member GivenIDs return updated member lists
    owners, editors, followers = hotlist_helpers.MembersWithGivenIDs(
        h, {1, 4, 7}, 'editor')
    self.assertEqual(owners, [2, 3])
    self.assertEqual(editors, [5, 6, 1, 4, 7])
    self.assertEqual(followers, [8, 9])
