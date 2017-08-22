# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.issuebulkedit."""

import os
import unittest
import webapp2

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import testbed

from framework import exceptions
from framework import permissions
from proto import tracker_pb2
from services import service_manager
from services import tracker_fulltext
from testing import fake
from testing import testing_helpers
from tracker import issuebulkedit
from tracker import tracker_bizobj


class Response(object):

  def __init__(self):
    self.status = None


class IssueBulkEditTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        features=fake.FeaturesService(),
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        issue_star=fake.IssueStarService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.servlet = issuebulkedit.IssueBulkEdit(
        'req', 'res', services=self.services)
    self.mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.project = self.services.project.TestAddProject(
        name='proj', project_id=789, owner_ids=[111])
    self.cnxn = 'fake connection'
    self.config = self.services.config.GetProjectConfig(
        self.cnxn, self.project.project_id)
    self.services.config.StoreConfig(self.cnxn, self.config)
    self.owner = self.services.user.TestAddUser('owner@example.com', 111)

    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_taskqueue_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    self.taskqueue_stub._root_path = os.path.dirname(
        os.path.dirname(os.path.dirname( __file__ )))

    self.mocked_methods = {}

  def tearDown(self):
    """Restore mocked objects of other modules."""
    for obj, items in self.mocked_methods.iteritems():
        for member, previous_value in items.iteritems():
          setattr(obj, member, previous_value)

  def testAssertBasePermission(self):
    """Permit users with EDIT_ISSUE and ADD_ISSUE_COMMENT permissions."""
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    self.servlet.AssertBasePermission(self.mr)

  def testGatherPageData(self):
    """Test GPD works in a normal no-corner-cases case."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', None,
        [], [], [], [], 111L, 'test issue')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project)
    mr.local_id_list = [local_id_1]

    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(1, page_data['num_issues'])

  def testGatherPageData_NoIssues(self):
    """Test GPD when no issues are specified in the mr."""
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project)
    self.assertRaises(exceptions.InputException,
                      self.servlet.GatherPageData, mr)

  def testGatherPageData_FilteredIssues(self):
    """Test GPD when all specified issues get filtered out."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', None, [],
        ['restrict-view-Googler'], [], [],
        111L, 'test issue')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project)
    mr.local_id_list = [local_id_1]

    self.assertRaises(webapp2.HTTPException,
                      self.servlet.GatherPageData, mr)

  def testGatherPageData_TypeLabels(self):
    """Test that GPD displays a custom field for appropriate issues."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', None, [],
        ['type-customlabels'], [], [],
        111L, 'test issue')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project)
    mr.local_id_list = [local_id_1]

    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.append(fd)

    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(1, len(page_data['fields']))

  def testProcessFormData(self):
    """Test that PFD works in a normal no-corner-cases case."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', 111L,
        [], [], [], [], 111L, 'test issue')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [local_id_1]

    post_data = fake.PostData(
        owner=['owner@example.com'], can=[1],
        q=[''], colspec=[''], sort=[''], groupby=[''], start=[0], num=[100])
    self._MockMethods()
    url = self.servlet.ProcessFormData(mr, post_data)
    self.assertTrue('list?can=1&q=&saved=1' in url)

  def testProcessFormData_NoIssues(self):
    """Test PFD when no issues are specified."""
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    post_data = fake.PostData()
    self.servlet.response = Response()
    self.servlet.ProcessFormData(mr, post_data)
    # 400 == bad request
    self.assertEqual(400, self.servlet.response.status)

  def testProcessFormData_NoUser(self):
    """Test PDF when the user is not logged in."""
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project)
    mr.local_id_list = [99999]
    post_data = fake.PostData()
    self.servlet.response = Response()
    self.servlet.ProcessFormData(mr, post_data)
    # 400 == bad request
    self.assertEqual(400, self.servlet.response.status)

  def testProcessFormData_CantComment(self):
    """Test PFD when the user can't comment on any of the issues."""
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.EMPTY_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [99999]
    post_data = fake.PostData()
    self.servlet.response = Response()
    self.servlet.ProcessFormData(mr, post_data)
    # 400 == bad request
    self.assertEqual(400, self.servlet.response.status)

  def testProcessFormData_CantEdit(self):
    """Test PFD when the user can't edit any issue metadata."""
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [99999]
    post_data = fake.PostData()
    self.servlet.response = Response()
    self.servlet.ProcessFormData(mr, post_data)
    # 400 == bad request
    self.assertEqual(400, self.servlet.response.status)

  def testProcessFormData_CantMove(self):
    """Test PFD when the user can't move issues."""
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [99999]
    post_data = fake.PostData(move_to=['proj'])
    self.servlet.response = Response()
    self.servlet.ProcessFormData(mr, post_data)
    # 400 == bad request
    self.assertEqual(400, self.servlet.response.status)

    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', 111L,
        [], [], [], [], 111L, 'test issue')
    mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    mr.local_id_list = [local_id_1]
    mr.project_name = 'proj'
    self._MockMethods()
    self.servlet.ProcessFormData(mr, post_data)
    self.assertEqual(
        'The issues are already in project proj', mr.errors.move_to)

    post_data = fake.PostData(move_to=['notexist'])
    self.servlet.ProcessFormData(mr, post_data)
    self.assertEqual('No such project: notexist', mr.errors.move_to)

  def _MockMethods(self):
    # Mock methods of other modules to avoid unnecessary testing
    self.mocked_methods[tracker_fulltext] = {
        'IndexIssues': tracker_fulltext.IndexIssues,
        'UnindexIssues': tracker_fulltext.UnindexIssues}
    def DoNothing(*_args, **_kwargs):
      pass
    self.servlet.PleaseCorrect = DoNothing
    tracker_fulltext.IndexIssues = DoNothing
    tracker_fulltext.UnindexIssues = DoNothing

  def VerifyIssueUpdated(self, project_id, local_id):
    issue = self.services.issue.GetIssueByLocalID(
        self.cnxn, project_id, local_id)
    issue_id = issue.issue_id
    comments = self.services.issue.GetCommentsForIssue(self.cnxn, issue_id)
    last_comment = comments[-1]
    return last_comment.amendments[0].newvalue == 'Updated'

  def testProcessFormData_CustomFields(self):
    """Test PFD processes edits to custom fields."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', 111L,
        [], [], [], [], 111L, 'test issue')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [local_id_1]

    fd = tracker_bizobj.MakeFieldDef(
        12345, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.append(fd)

    post_data = fake.PostData(
        custom_12345=['111'], owner=['owner@example.com'], can=[1],
        q=[''], colspec=[''], sort=[''], groupby=[''], start=[0], num=[100])
    self._MockMethods()
    self.servlet.ProcessFormData(mr, post_data)
    self.assertTrue(self.VerifyIssueUpdated(789, local_id_1))

  def testProcessFormData_DuplicateStatus_MergeSameIssue(self):
    """Test PFD processes null/cleared status values."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id, 'issue summary',
        'New', 111L, [], [], [], [], 111L, 'test issue')
    merge_into_local_id_2 = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id, 'issue summary2',
        'New', 112L, [], [], [], [], 112L, 'test issue2')

    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [local_id_1, merge_into_local_id_2]
    mr.project_name = 'proj'

    # Add required project_name to merge_into_issue.
    merge_into_issue = self.services.issue.GetIssueByLocalID(
        mr.cnxn, self.project.project_id, merge_into_local_id_2)
    merge_into_issue.project_name = 'proj'

    post_data = fake.PostData(status=['Duplicate'],
        merge_into=[str(merge_into_local_id_2)], owner=['owner@example.com'],
        can=[1], q=[''], colspec=[''], sort=[''], groupby=[''], start=[0],
        num=[100])
    self._MockMethods()
    self.servlet.ProcessFormData(mr, post_data)
    self.assertEquals('Cannot merge issue into itself', mr.errors.merge_into_id)

  def testProcessFormData_DuplicateStatus_MergeMissingIssue(self):
    """Test PFD processes null/cleared status values."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id, 'issue summary',
        'New', 111L, [], [], [], [], 111L, 'test issue')
    local_id_2 = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id, 'issue summary2',
        'New', 112L, [], [], [], [], 112L, 'test issue2')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [local_id_1, local_id_2]
    mr.project_name = 'proj'

    post_data = fake.PostData(status=['Duplicate'],
        merge_into=['non existant id'], owner=['owner@example.com'],
        can=[1], q=[''], colspec=[''], sort=[''], groupby=[''], start=[0],
        num=[100])
    self._MockMethods()
    self.servlet.ProcessFormData(mr, post_data)
    self.assertEquals('Please enter an issue ID',
                      mr.errors.merge_into_id)

  def testProcessFormData_DuplicateStatus_Success(self):
    """Test PFD processes null/cleared status values."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id, 'issue summary',
        'New', 111L, [], [], [], [], 111L, 'test issue')
    local_id_2 = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id, 'issue summary2',
        'New', 111L, [], [], [], [], 111L, 'test issue2')
    merge_into_local_id_3 = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id, 'issue summary3',
        'New', 112L, [], [], [], [], 112L, 'test issue3')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [local_id_1, local_id_2]
    mr.project_name = 'proj'

    post_data = fake.PostData(status=['Duplicate'],
        merge_into=[str(merge_into_local_id_3)], owner=['owner@example.com'],
        can=[1], q=[''], colspec=[''], sort=[''], groupby=[''], start=[0],
        num=[100])
    self._MockMethods()

    # Add project_name, CCs and starrers to the merge_into_issue.
    merge_into_issue = self.services.issue.GetIssueByLocalID(
        mr.cnxn, self.project.project_id, merge_into_local_id_3)
    merge_into_issue.project_name = 'proj'
    merge_into_issue.cc_ids = [113L, 120L]
    self.services.issue_star.SetStar(
        mr.cnxn, None, None, merge_into_issue.issue_id, 120L, True)

    # Add project_name, CCs and starrers to the source issues.
    # Issue 1
    issue_1 = self.services.issue.GetIssueByLocalID(
        mr.cnxn, self.project.project_id, local_id_1)
    issue_1.project_name = 'proj'
    issue_1.cc_ids = [113L, 114L]
    self.services.issue_star.SetStar(
        mr.cnxn, None, None, issue_1.issue_id, 113L, True)
    # Issue 2
    issue_2 = self.services.issue.GetIssueByLocalID(
        mr.cnxn, self.project.project_id, local_id_2)
    issue_2.project_name = 'proj'
    issue_2.cc_ids = [113L, 115L, 118L]
    self.services.issue_star.SetStar(
        mr.cnxn, None, None, issue_2.issue_id, 114L, True)
    self.services.issue_star.SetStar(
        mr.cnxn, None, None, issue_2.issue_id, 115L, True)

    self.servlet.ProcessFormData(mr, post_data)

    # Verify both source issues were updated.
    self.assertTrue(
        self.VerifyIssueUpdated(self.project.project_id, local_id_1))
    self.assertTrue(
        self.VerifyIssueUpdated(self.project.project_id, local_id_2))

    # Verify that the merge into issue was updated with a comment.
    comments = self.services.issue.GetCommentsForIssue(
        self.cnxn, merge_into_issue.issue_id)
    self.assertEquals(
        'Issue 1 has been merged into this issue.\n'
        'Issue 2 has been merged into this issue.', comments[-1].content)

    # Verify CC lists and owner were merged to the merge_into issue.
    self.assertEquals(
            [113L, 120L, 114L, 115L, 118L, 111L], merge_into_issue.cc_ids)
    # Verify new starrers were added to the merge_into issue.
    self.assertEquals(4,
                      self.services.issue_star.CountItemStars(
                          self.cnxn, merge_into_issue.issue_id))
    self.assertEquals([120L, 113L, 114L, 115L],
                      self.services.issue_star.LookupItemStarrers(
                          self.cnxn, merge_into_issue.issue_id))

  def testProcessFormData_ClearStatus(self):
    """Test PFD processes null/cleared status values."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', 111L,
        [], [], [], [], 111L, 'test issue')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [local_id_1]

    post_data = fake.PostData(
        op_statusenter=['clear'], owner=['owner@example.com'], can=[1],
        q=[''], colspec=[''], sort=[''], groupby=[''], start=[0], num=[100])
    self._MockMethods()
    self.servlet.ProcessFormData(mr, post_data)
    self.assertTrue(self.VerifyIssueUpdated(789, local_id_1))

  def testProcessFormData_InvalidOwner(self):
    """Test PFD rejects invalid owner emails."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', None,
        [], [], [], [], 111L, 'test issue')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.local_id_list = [local_id_1]
    post_data = fake.PostData(
        owner=['invalid'])
    self.servlet.response = Response()
    self._MockMethods()
    self.servlet.ProcessFormData(mr, post_data)
    self.assertTrue(mr.errors.AnyErrors())

  def testProcessFormData_MoveTo(self):
    """Test PFD processes move_to values."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue to move', 'New', 111L,
        [], [], [], [], 111L, 'test issue')
    move_to_project = self.services.project.TestAddProject(
        name='proj2', project_id=790, owner_ids=[111])

    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.project_name = 'proj'
    mr.local_id_list = [local_id_1]

    self._MockMethods()
    post_data = fake.PostData(
        move_to=['proj2'], can=[1], q=[''],
        colspec=[''], sort=[''], groupby=[''], start=[0], num=[100])
    self.servlet.response = Response()
    self.servlet.ProcessFormData(mr, post_data)

    issue = self.services.issue.GetIssueByLocalID(
        self.cnxn, move_to_project.project_id, local_id_1)
    self.assertIsNotNone(issue)

  def testProcessFormData_InvalidBlockIssues(self):
    """Test PFD processes invalid blocked_on and blocking values."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', 111L,
        [], [], [], [], 111L, 'test issue')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.project_name = 'proj'
    mr.local_id_list = [local_id_1]

    self._MockMethods()
    post_data = fake.PostData(
        op_blockedonenter=['append'], blocked_on=['12345'],
        op_blockingenter=['append'], blocking=['54321'],
        can=[1], q=[''],
        colspec=[''], sort=[''], groupby=[''], start=[0], num=[100])
    self.servlet.ProcessFormData(mr, post_data)

    self.assertEqual('Invalid issue ID 12345', mr.errors.blocked_on)
    self.assertEqual('Invalid issue ID 54321', mr.errors.blocking)

  def testProcessFormData_NormalBlockIssues(self):
    """Test PFD processes blocked_on and blocking values."""
    local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'issue summary', 'New', 111L,
        [], [], [], [], 111L, 'test issue')
    blocking_id = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'blocking', 'New', 111L,
        [], [], [], [], 111L, 'test issue')
    blocked_on_id = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'blocked on', 'New', 111L,
        [], [], [], [], 111L, 'test issue')
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id': 111})
    mr.project_name = 'proj'
    mr.local_id_list = [local_id_1]

    self._MockMethods()
    post_data = fake.PostData(
        op_blockedonenter=['append'], blocked_on=[str(blocked_on_id)],
        op_blockingenter=['append'], blocking=[str(blocking_id)],
        can=[1], q=[''],
        colspec=[''], sort=[''], groupby=[''], start=[0], num=[100])
    self.servlet.ProcessFormData(mr, post_data)

    self.assertIsNone(mr.errors.blocked_on)
    self.assertIsNone(mr.errors.blocking)
