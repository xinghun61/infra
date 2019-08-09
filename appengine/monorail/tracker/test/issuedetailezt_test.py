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


class IssueDetailTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        issue_star=fake.IssueStarService(),
        spam=fake.SpamService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.config = tracker_pb2.ProjectIssueConfig()
    self.config.statuses_offer_merge.append('Duplicate')
    self.services.config.StoreConfig(self.cnxn, self.config)



  def testChooseNextPage(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail_ezt?id=123&q=term')
    mr.col_spec = ''
    config = tracker_pb2.ProjectIssueConfig()
    issue = fake.MakeTestIssue(987, 123, 'summary', 'New', 111)

    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, None, None,
        user_pb2.IssueUpdateNav.UP_TO_LIST, '124')
    self.assertTrue(url.startswith(
        'http://127.0.0.1/p/proj/issues/list?cursor=proj%3A123&q=term'))
    self.assertTrue(url.endswith('&updated=123'))

    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, None, None,
        user_pb2.IssueUpdateNav.STAY_SAME_ISSUE, '124')
    self.assertEqual('http://127.0.0.1/p/proj/issues/detail_ezt?id=123&q=term',
                     url)

    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, None, None,
        user_pb2.IssueUpdateNav.NEXT_IN_LIST, '124')
    self.assertEqual('http://127.0.0.1/p/proj/issues/detail_ezt?id=124&q=term',
                     url)

    # If this is the last in the list, the next_id from the form will be ''.
    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, None, None,
        user_pb2.IssueUpdateNav.NEXT_IN_LIST, '')
    self.assertTrue(url.startswith(
        'http://127.0.0.1/p/proj/issues/list?cursor=proj%3A123&q=term'))
    self.assertTrue(url.endswith('&updated=123'))

  def testChooseNextPage_ForMoveRequest(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail_ezt?id=123&q=term')
    mr.col_spec = ''
    config = tracker_pb2.ProjectIssueConfig()
    issue = fake.MakeTestIssue(987, 123, 'summary', 'New', 111)
    moved_to_project_name = 'projB'
    moved_to_project_local_id = 543
    moved_to_project_name_and_local_id = (moved_to_project_name,
                                          moved_to_project_local_id)

    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, moved_to_project_name_and_local_id, None,
        user_pb2.IssueUpdateNav.UP_TO_LIST, '124')
    self.assertTrue(url.startswith(
        'http://127.0.0.1/p/proj/issues/list?cursor=proj%3A123&moved_to_id=' +
        str(moved_to_project_local_id) + '&moved_to_project=' +
        moved_to_project_name + '&q=term'))

    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, moved_to_project_name_and_local_id, None,
        user_pb2.IssueUpdateNav.STAY_SAME_ISSUE, '124')
    self.assertEqual(
        'http://127.0.0.1/p/%s/issues/detail_ezt?id=123&q=term' % (
            moved_to_project_name),
        url)
    mr.project_name = 'proj'  # reset project name back.

    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, moved_to_project_name_and_local_id, None,
        user_pb2.IssueUpdateNav.NEXT_IN_LIST, '124')
    self.assertEqual('http://127.0.0.1/p/proj/issues/detail_ezt?id=124&q=term',
                     url)

    # If this is the last in the list, the next_id from the form will be ''.
    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, moved_to_project_name_and_local_id, None,
        user_pb2.IssueUpdateNav.NEXT_IN_LIST, '')
    self.assertTrue(url.startswith(
        'http://127.0.0.1/p/proj/issues/list?cursor=proj%3A123&moved_to_id=' +
        str(moved_to_project_local_id) + '&moved_to_project=' +
        moved_to_project_name + '&q=term'))

  def testChooseNextPage_ForCopyRequest(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail_ezt?id=123&q=term')
    mr.col_spec = ''
    config = tracker_pb2.ProjectIssueConfig()
    issue = fake.MakeTestIssue(987, 123, 'summary', 'New', 111)
    copied_to_project_name = 'projB'
    copied_to_project_local_id = 543
    copied_to_project_name_and_local_id = (copied_to_project_name,
                                           copied_to_project_local_id)

    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, None, copied_to_project_name_and_local_id,
        user_pb2.IssueUpdateNav.UP_TO_LIST, '124')
    self.assertTrue(url.startswith(
        'http://127.0.0.1/p/proj/issues/list?copied_from_id=123'
        '&copied_to_id=' + str(copied_to_project_local_id) +
        '&copied_to_project=' + copied_to_project_name +
        '&cursor=proj%3A123&q=term'))

    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, None, copied_to_project_name_and_local_id,
        user_pb2.IssueUpdateNav.STAY_SAME_ISSUE, '124')
    self.assertEqual('http://127.0.0.1/p/proj/issues/detail_ezt?id=123&q=term',
                     url)
    mr.project_name = 'proj'  # reset project name back.

    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, None, copied_to_project_name_and_local_id,
        user_pb2.IssueUpdateNav.NEXT_IN_LIST, '124')
    self.assertEqual('http://127.0.0.1/p/proj/issues/detail_ezt?id=124&q=term',
                     url)

    # If this is the last in the list, the next_id from the form will be ''.
    url = issuedetailezt._ChooseNextPage(
        mr, issue.local_id, config, None, copied_to_project_name_and_local_id,
        user_pb2.IssueUpdateNav.NEXT_IN_LIST, '')
    self.assertTrue(url.startswith(
        'http://127.0.0.1/p/proj/issues/list?copied_from_id=123'
        '&copied_to_id=' + str(copied_to_project_local_id) +
        '&copied_to_project=' + copied_to_project_name +
        '&cursor=proj%3A123&q=term'))

  def testGatherHelpData_Anon(self):
    servlet = issuedetailezt.IssueDetailEzt(
        'req', 'res', services=self.services)
    mr = testing_helpers.MakeMonorailRequest()
    mr.auth.user_id = 0

    # Anon users do not see dismissable cues unless there is something relevant
    # in the page_data to trigger it.
    help_data = servlet.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])

  def testGatherHelpData_SignedIn(self):
    servlet = issuedetailezt.IssueDetailEzt(
        'req', 'res', services=self.services)
    mr = testing_helpers.MakeMonorailRequest()
    mr.auth.user_id = 111

    # User needs to click through the privacy dialog.
    help_data = servlet.GatherHelpData(mr, {})
    self.assertEqual('privacy_click_through', help_data['cue'])

    # And, the code of conduct cue card.
    self.services.user.SetUserPrefs(
        'cnxn', 111,
        [user_pb2.UserPrefValue(name='privacy_click_through', value='true')])
    help_data = servlet.GatherHelpData(mr, {})
    self.assertEqual('code_of_conduct', help_data['cue'])

    mr.auth.user_pb.dismissed_cues = [
        'privacy_click_through', 'code_of_conduct']
    self.services.user.SetUserPrefs(
        'cnxn', 111,
        [user_pb2.UserPrefValue(name='privacy_click_through', value='true'),
         user_pb2.UserPrefValue(name='code_of_conduct', value='true')])
    # User did not jump to an issue, no query at all.
    help_data = servlet.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])

    # User did not jump to an issue, query was not a local ID number.
    mr.query = 'memory leak'
    help_data = servlet.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])

    # User jumped directly to an issue, maybe they meant to search instead.
    mr.query = '123'
    help_data = servlet.GatherHelpData(mr, {})
    self.assertEqual('search_for_numbers', help_data['cue'])
    self.assertEqual(123, help_data['jump_local_id'])

    # User is viewing an issue with an unavailable owner.
    mr.query = ''
    issue_view = testing_helpers.Blank(
        is_spam=False,
        owner=testing_helpers.Blank(user_id=111, avail_message='On vacation'),
        derived_owner=testing_helpers.Blank(user_id=0, avail_message=''),
        cc=[testing_helpers.Blank(user_id=222, avail_message='')],
        derived_cc=[testing_helpers.Blank(user_id=333, avail_message='')])
    page_data = {'issue': issue_view}
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertEqual('availability_msgs', help_data['cue'])

    # User is viewing an issue with all participants available.
    # No help cue is shown.
    issue_view = testing_helpers.Blank(
        is_spam=False,
        owner=testing_helpers.Blank(user_id=0, avail_message='Never visited'),
        derived_owner=testing_helpers.Blank(user_id=0, avail_message=''),
        cc=[testing_helpers.Blank(user_id=222, avail_message='')],
        derived_cc=[testing_helpers.Blank(user_id=333, avail_message='')])
    page_data = {'issue': issue_view}
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertEqual(None, help_data['cue'])


class IssueDetailFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.project_name = 'proj'
    self.project_id = 987
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        features=fake.FeaturesService(),
        issue=fake.IssueService(),
        issue_star=fake.IssueStarService(),
        project=fake.ProjectService(),
        spam=fake.SpamService(),
        user=fake.UserService())
    self.project = self.services.project.TestAddProject(
      'proj', project_id=987, committer_ids=[111])
    self.servlet = issuedetailezt.IssueDetailEzt(
        'req', 'res', services=self.services)
    self.mox = mox.Mox()
    self.services.user.TestAddUser('owner@example.com', 111)
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'sum', 'New', 111, project_name='proj')

    self.original_GetAdjacentIssue = issuedetailezt.GetAdjacentIssue
    issuedetailezt.GetAdjacentIssue = mock.Mock()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()
    issuedetailezt.GetAdjacentIssue = self.original_GetAdjacentIssue

  def testGatherPageData_ApprovalRedirect(self):
    self.servlet.redirect = mock.Mock()
    approval_values = [tracker_pb2.ApprovalValue(approval_id=23, phase_id=1)]
    self.issue.approval_values = approval_values
    self.services.issue.TestAddIssue(self.issue)
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project, path='/p/proj/issues/detail?id=%d' %
            self.issue.local_id)
    mr.auth.user_id = 111

    framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_APPROVAL, id=self.issue.local_id)
    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/948222
    # self.servlet.redirect.assert_called_once()

  def testFieldEditPermitted_NoEdit(self):
    page_perms = testing_helpers.Blank(
        EditIssueSummary=False, EditIssueStatus=False, EditIssueOwner=False,
        EditIssueCc=False)  # no perms are needed.
    self.assertTrue(issuedetailezt._FieldEditPermitted(
        [], '', '', '', '', 0, [], page_perms))

  def testFieldEditPermitted_AllNeededPerms(self):
    page_perms = testing_helpers.Blank(
        EditIssueSummary=True, EditIssueStatus=True, EditIssueOwner=True,
        EditIssueCc=True)
    self.assertTrue(issuedetailezt._FieldEditPermitted(
        [], '', '', 'new sum', 'new status', 111, [222], page_perms))

  def testFieldEditPermitted_MissingPerms(self):
    page_perms = testing_helpers.Blank(
        EditIssueSummary=False, EditIssueStatus=False, EditIssueOwner=False,
        EditIssueCc=False)  # no perms.
    self.assertFalse(issuedetailezt._FieldEditPermitted(
        [], '', '', 'new sum', '', 0, [], page_perms))
    self.assertFalse(issuedetailezt._FieldEditPermitted(
        [], '', '', '', 'new status', 0, [], page_perms))
    self.assertFalse(issuedetailezt._FieldEditPermitted(
        [], '', '', '', '', 111, [], page_perms))
    self.assertFalse(issuedetailezt._FieldEditPermitted(
        [], '', '', '', '', 0, [222], page_perms))

  def testFieldEditPermitted_NeededPermsNotOffered(self):
    """Even if user has all the field-level perms, they still can't do this."""
    page_perms = testing_helpers.Blank(
        EditIssueSummary=True, EditIssueStatus=True, EditIssueOwner=True,
        EditIssueCc=True)
    self.assertFalse(issuedetailezt._FieldEditPermitted(
        ['NewLabel'], '', '', '', '', 0, [], page_perms))
    self.assertFalse(issuedetailezt._FieldEditPermitted(
        [], 'new blocked on', '', '', '', 0, [], page_perms))
    self.assertFalse(issuedetailezt._FieldEditPermitted(
        [], '', 'new blocking', '', '', 0, [], page_perms))

  def testValidateOwner_ChangedToValidOwner(self):
    post_data_owner = 'superman@krypton.com'
    parsed_owner_id = 111
    original_issue_owner_id = 111
    mr = testing_helpers.MakeMonorailRequest(project=self.project)

    self.mox.StubOutWithMock(tracker_helpers, 'IsValidIssueOwner')
    tracker_helpers.IsValidIssueOwner(
        mr.cnxn, mr.project, parsed_owner_id, self.services).AndReturn(
            (True, ''))
    self.mox.ReplayAll()

    ret = self.servlet._ValidateOwner(
        mr, post_data_owner, parsed_owner_id, original_issue_owner_id)
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testValidateOwner_UnchangedInvalidOwner(self):
    post_data_owner = 'superman@krypton.com'
    parsed_owner_id = 111
    original_issue_owner_id = 111
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    self.services.user.TestAddUser(post_data_owner, original_issue_owner_id)

    self.mox.StubOutWithMock(tracker_helpers, 'IsValidIssueOwner')
    tracker_helpers.IsValidIssueOwner(
        mr.cnxn, mr.project, parsed_owner_id, self.services).AndReturn(
            (False, 'invalid owner'))
    self.mox.ReplayAll()

    ret = self.servlet._ValidateOwner(
        mr, post_data_owner, parsed_owner_id, original_issue_owner_id)
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testValidateOwner_ChangedFromValidToInvalidOwner(self):
    post_data_owner = 'lexluthor'
    parsed_owner_id = 111
    original_issue_owner_id = 111
    original_issue_owner = 'superman@krypton.com'
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    self.services.user.TestAddUser(original_issue_owner,
                                   original_issue_owner_id)

    self.mox.StubOutWithMock(tracker_helpers, 'IsValidIssueOwner')
    tracker_helpers.IsValidIssueOwner(
        mr.cnxn, mr.project, parsed_owner_id, self.services).AndReturn(
            (False, 'invalid owner'))
    self.mox.ReplayAll()

    ret = self.servlet._ValidateOwner(
        mr, post_data_owner, parsed_owner_id, original_issue_owner_id)
    self.mox.VerifyAll()
    self.assertEquals('invalid owner', ret)

  def testValidateCC(self):
    cc_ids = [1, 2]
    cc_names = ['user1@example', 'user2@example']
    res = self.servlet._ValidateCC(cc_ids, cc_names)
    self.assertIsNone(res)

    cc_ids = [None, 2]
    res = self.servlet._ValidateCC(cc_ids, cc_names)
    self.assertEqual(res, 'Invalid Cc username: user1@example')

  def testProcessFormData_NoPermission(self):
    """Anonymous users and users without ADD_ISSUE_COMMENT cannot comment."""
    local_id_1, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id,
        'summary_1', 'status', 111, [], [], [], [], 111, 'description_1')
    _, mr = testing_helpers.GetRequestObjects(
        project=self.project,
        perms=permissions.CONTRIBUTOR_INACTIVE_PERMISSIONSET)
    mr.auth.user_id = 0
    mr.local_id = local_id_1
    self.assertRaises(permissions.PermissionException,
                      self.servlet.ProcessFormData, mr, {})
    mr.auth.user_id = 111
    self.assertRaises(permissions.PermissionException,
                      self.servlet.ProcessFormData, mr, {})

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testProcessFormData_NonMembersCantEdit(self, _mock_prepsend):
    """Non-members can comment, but never affect issue fields."""
    local_id_1, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id,
        'summary_1', 'status', 111, [], [], [], [], 111, 'description_1')
    local_id_2, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id,
        'summary_2', 'status', 111, [], [], [], [], 111, 'description_2')

    _amendments, _cmnt_pb = self.services.issue.ApplyIssueComment(
        self.cnxn, self.services, 111,
        self.project.project_id, local_id_2, 'summary', 'Duplicate', 111,
        [], [], [], [], [], [], [], [], local_id_1,
        comment='closing as a dup of 1')

    non_member_user_id = 999
    post_data = fake.PostData({
        'merge_into': [''],  # non-member tries to remove merged_into
        'comment': ['thanks!'],
        'can': ['1'],
        'q': ['foo'],
        'colspec': ['bar'],
        'sort': 'baz',
        'groupby': 'qux',
        'start': ['0'],
        'num': ['100'],
        'pagegen': [str(int(time.time()) + 1)],
        })

    _, mr = testing_helpers.GetRequestObjects(
        user_info={'user_id': non_member_user_id},
        path='/p/proj/issues/detail_ezt.do?id=%d' % local_id_2,
        project=self.project, method='POST',
        perms=permissions.USER_PERMISSIONSET)
    mr.project_name = self.project.project_name
    mr.project = self.project
    mr.me_user_id = 111

    self.mox.ReplayAll()

    # The form should be processed and redirect back to viewing the issue.
    redirect_url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertTrue(redirect_url.startswith(
        'http://127.0.0.1/p/proj/issues/detail_ezt?id=%d' % local_id_2))

    # BUT, issue should not have been edited because user lacked permission.
    updated_issue_2 = self.services.issue.GetIssueByLocalID(
        self.cnxn, self.project.project_id, local_id_2)
    self.assertEqual(local_id_1, updated_issue_2.merged_into)

    self.assertIs(issuedetailezt.GetAdjacentIssue.called, True)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testProcessFormData_NewMemberExistingFormOnlyAddsComment(
      self, _mock_prepsend):
    """Non-member had a form open, then become a member, then submitted."""
    self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id,
        'summary_1', 'status', 111, [], [], [], [], 111, 'description_1')
    local_id_2, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id,
        'summary_2', 'status', 111, [], [], [], [], 111, 'description_2')

    non_member_user_id = 999
    post_data = fake.PostData({
        # non-member form has no summary field, so it defaults to ''.
        'fields_not_offered': 'True',
        'comment': ['thanks!'],
        'can': ['1'],
        'q': ['foo'],
        'colspec': ['bar'],
        'sort': 'baz',
        'groupby': 'qux',
        'start': ['0'],
        'num': ['100'],
        'pagegen': [str(int(time.time()) + 1)],
        })

    _, mr = testing_helpers.GetRequestObjects(
        user_info={'user_id': non_member_user_id},
        path='/p/proj/issues/detail_ezt.do?id=%d' % local_id_2,
        project=self.project, method='POST',
        # The user has suddenly become a member.
        perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    mr.project_name = self.project.project_name
    mr.project = self.project
    mr.me_user_id = 111

    self.mox.ReplayAll()

    # The form should be processed and redirect back to viewing the issue.
    redirect_url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()

    self.assertIs(issuedetailezt.GetAdjacentIssue.called, True)

    self.assertTrue(redirect_url.startswith(
        'http://127.0.0.1/p/proj/issues/detail_ezt?id=%d' % local_id_2))

    # BUT, issue should not have been edited because editing fields were not
    # offered when the form was generated.
    updated_issue_2 = self.services.issue.GetIssueByLocalID(
        self.cnxn, self.project.project_id, local_id_2)
    self.assertEqual('summary_2', updated_issue_2.summary)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  @mock.patch(
      'tracker.tracker_helpers.GetNewIssueStarrers')
  def testProcessFormData_DuplicateAddsACommentToTarget(
      self, _mock_getstarrers, _mock_prepsend):
    """Marking issue 2 as dup of 1 adds a comment to 1."""
    local_id_1, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id,
        'summary_1', 'New', 111, [], [], [], [], 111, 'description_1')
    issue_1 = self.services.issue.GetIssueByLocalID(
        self.cnxn, self.project.project_id, local_id_1)
    issue_1.project_name = 'proj'
    local_id_2, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id,
        'summary_2', 'New', 111, [], [], [], [], 111, 'description_2')
    issue_2 = self.services.issue.GetIssueByLocalID(
        self.cnxn, self.project.project_id, local_id_2)
    issue_2.project_name = 'proj'

    post_data = fake.PostData({
        'status': ['Duplicate'],
        'merge_into': [str(local_id_1)],
        'comment': ['marking as dup'],
        'can': ['1'],
        'q': ['foo'],
        'colspec': ['bar'],
        'sort': 'baz',
        'groupby': 'qux',
        'start': ['0'],
        'num': ['100'],
        'pagegen': [str(int(time.time()) + 1)],
        })

    member_user_id = 111
    _, mr = testing_helpers.GetRequestObjects(
        user_info={'user_id': member_user_id},
        path='/p/proj/issues/detail_ezt.do?id=%d' % local_id_2,
        project=self.project, method='POST',
        perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    mr.project_name = self.project.project_name
    mr.project = self.project
    mr.me_user_id = 111

    # The form should be processed and redirect back to viewing the issue.
    self.servlet.ProcessFormData(mr, post_data)

    self.assertEqual('Duplicate', issue_2.status)
    self.assertEqual(issue_1.issue_id, issue_2.merged_into)
    comments_1 = self.services.issue.GetCommentsForIssue(
        self.cnxn, issue_1.issue_id)
    self.assertEqual(2, len(comments_1))
    self.assertEqual(
        'Issue 2 has been merged into this issue.',
        comments_1[1].content)

    # Making another comment on issue 2 does not affect issue 1.
    self.servlet.ProcessFormData(mr, post_data)
    comments_1 = self.services.issue.GetCommentsForIssue(
        self.cnxn, issue_1.issue_id)
    self.assertEqual(2, len(comments_1))

    self.assertIs(issuedetailezt.GetAdjacentIssue.called, True)

    # TODO(jrobbins): add more unit tests for other aspects of ProcessForm.

  @mock.patch('services.tracker_fulltext.IndexIssues')
  def testHandleCopyOrMove_Copy_SameProject(self, _mock_indexissues):
    _, mr = testing_helpers.GetRequestObjects(
        user_info={'user_id': 222},
        path='/p/proj/issues/detail_ezt.do?id=1',
        project=self.project, method='POST',
        perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    mr.project_name = self.project.project_name
    mr.project = self.project
    self.services.issue.TestAddIssue(self.issue)

    self.servlet.HandleCopyOrMove(
        'cnxn', mr, self.project, self.issue, False, False)

    copied_issue = self.services.issue.GetIssueByLocalID(
        'cnxn', self.project.project_id, 2)
    self.assertEqual(self.issue.project_id, copied_issue.project_id)
    self.assertEqual(self.issue.summary, copied_issue.summary)
    self.assertEqual(copied_issue.reporter_id, 222)

  @mock.patch('services.tracker_fulltext.IndexIssues')
  def testHandleCopyOrMove_Copy_DifferentProject(self, _mock_indexissues):
    _, mr = testing_helpers.GetRequestObjects(
        user_info={'user_id': 222},
        path='/p/proj/issues/detail_ezt.do?id=1',
        project=self.project, method='POST',
        perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    mr.project_name = self.project.project_name
    mr.project = self.project
    self.services.issue.TestAddIssue(self.issue)
    dest_project = self.services.project.TestAddProject(
      'dest', project_id=988, committer_ids=[111])

    self.servlet.HandleCopyOrMove(
        'cnxn', mr, dest_project, self.issue, False, False)

    copied_issue = self.services.issue.GetIssueByLocalID(
        'cnxn', dest_project.project_id, 1)
    self.assertEqual(self.project.project_id, self.issue.project_id)
    self.assertEqual(dest_project.project_id, copied_issue.project_id)
    self.assertEqual(self.issue.summary, copied_issue.summary)
    self.assertEqual(copied_issue.reporter_id, 222)

  @mock.patch('services.tracker_fulltext.IndexIssues')
  @mock.patch('services.tracker_fulltext.UnindexIssues')
  def testHandleCopyOrMove_Move_DifferentProject(
      self, _mock_unindexissues, _mock_indexissues):
    _, mr = testing_helpers.GetRequestObjects(
        user_info={'user_id': 222},
        path='/p/proj/issues/detail_ezt.do?id=1',
        project=self.project, method='POST',
        perms=permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    mr.project_name = self.project.project_name
    mr.project = self.project
    self.services.issue.TestAddIssue(self.issue)
    dest_project = self.services.project.TestAddProject(
      'dest', project_id=988, committer_ids=[111])

    self.servlet.HandleCopyOrMove(
        'cnxn', mr, dest_project, self.issue, False, True)

    moved_issue = self.services.issue.GetIssueByLocalID(
        'cnxn', dest_project.project_id, 1)
    self.assertEqual(dest_project.project_id, moved_issue.project_id)
    self.assertEqual(self.issue.summary, moved_issue.summary)
    self.assertEqual(moved_issue.reporter_id, 111)


class ModuleFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        features=fake.FeaturesService())
    self.cnxn = fake.MonorailConnection()

    # Set up for testing getBinnedHotlistViews.
    # Project p1; issue i1 in p1; user u1 owns i1; ui1 is an *involved* user.
    self.services.user.TestAddUser('u1', 111)
    project = self.services.project.TestAddProject('p1')
    issue_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, project_id=project.project_id,
        summary='summary', status='Open', owner_id=111, cc_ids=[], labels=[],
        field_values=[], component_ids=[], reporter_id=111,
        marked_description='marked description')
    self.issue_id = self.services.issue.LookupIssueID(
        self.cnxn, project_id=project.project_id, local_id=issue_local_id)
    # ul1 is a *logged in* user.
    self.services.user.TestAddUser('ul1', 222)
    # uo1 is an *other* user.
    self.services.user.TestAddUser('uo1', 333)
    self.perms = permissions.EMPTY_PERMISSIONSET

    users_by_id = self.services.user.GetUsersByIDs(self.cnxn,
                                                  [111, 222, 333])
    self.userviews_by_id = {k: framework_views.UserView(v)
        for k, v in users_by_id.items()}

    self.user_auth = authdata.AuthData.FromEmail(
        self.cnxn, 'ul1', self.services)

    self.hotlist_item_fields = [(self.issue_id, None, None, None, None)]

  def test_GetBinnedHotlistViews_IssueOwnerHasAHotlist(self):
    """user u1 owns h1 and the issue; h1 should go into the "involved" bin."""
    # Hotlist h1; user u1 owns h1; u1 is the issue reporter and owner, and so
    # is an *involved* user.
    hotlist_h1 = fake.Hotlist(hotlist_name='h1', hotlist_id=1, owner_ids=[111],
        hotlist_item_fields=self.hotlist_item_fields)
    h1_view = hotlist_views.HotlistView(
        hotlist_h1, self.perms, viewed_user_id=222, user_auth=self.user_auth,
        users_by_id=self.userviews_by_id)
    self.assertEqual(
        ([], [h1_view], []),
        issuedetailezt._GetBinnedHotlistViews([h1_view], involved_users=[111]))

  def test_GetBinnedHotlistViews_SignedInUserHasAHotlist(self):
    """user ul1 owns h2 and is logged in; h2 should go into the "user" bin"""
    # Hotlist h2; user ul1 owns h2; ul1 is a *logged in* user.
    hotlist_h2 = fake.Hotlist(hotlist_name='h2', hotlist_id=2, owner_ids=[222],
        hotlist_item_fields=self.hotlist_item_fields)
    h2_view = hotlist_views.HotlistView(
        hotlist_h2, self.perms, viewed_user_id=222, user_auth=self.user_auth,
        users_by_id=self.userviews_by_id)
    self.assertEqual(
        ([h2_view], [], []),
        issuedetailezt._GetBinnedHotlistViews([h2_view], involved_users=[111]))

  def test_GetBinnedHotlistViews_OtherUserHasAHotlist(self):
    """user uo1 owns h3; uo1 is an "other"; h3 should go into the "user" bin"""
    # Hotlist h3; user uo1 owns h3; uo3 is an *other* user.
    hotlist_h3 = fake.Hotlist(hotlist_name='h3', hotlist_id=3, owner_ids=[333],
        hotlist_item_fields=self.hotlist_item_fields)
    h3_view = hotlist_views.HotlistView(
        hotlist_h3, self.perms, viewed_user_id=222, user_auth=self.user_auth,
        users_by_id=self.userviews_by_id)
    self.assertEqual(
        ([], [], [h3_view]),
        issuedetailezt._GetBinnedHotlistViews([h3_view], involved_users=[111]))

  def test_GetBinnedHotlistViews_Empty(self):
    """When no hotlist views are passed in, all bins should be empty"""
    self.assertEqual(
        ([], [], []),
        issuedetailezt._GetBinnedHotlistViews([], involved_users=[111]))

  def test_GetBinnedHotlistViews_Multiple(self):
    """Should correctly bin each hotlist view when passed in multiple views"""
    hotlist_h1 = fake.Hotlist(hotlist_name='h1', hotlist_id=1, owner_ids=[111],
        hotlist_item_fields=self.hotlist_item_fields)
    h1_view = hotlist_views.HotlistView(
        hotlist_h1, self.perms, viewed_user_id=222, user_auth=self.user_auth,
        users_by_id=self.userviews_by_id)
    hotlist_h2 = fake.Hotlist(hotlist_name='h2', hotlist_id=2, owner_ids=[222],
        hotlist_item_fields=self.hotlist_item_fields)
    h2_view = hotlist_views.HotlistView(
        hotlist_h2, self.perms, viewed_user_id=222, user_auth=self.user_auth,
        users_by_id=self.userviews_by_id)
    hotlist_h3 = fake.Hotlist(hotlist_name='h3', hotlist_id=3, owner_ids=[333],
        hotlist_item_fields=self.hotlist_item_fields)
    h3_view = hotlist_views.HotlistView(
        hotlist_h3, self.perms, viewed_user_id=222, user_auth=self.user_auth,
        users_by_id=self.userviews_by_id)
    self.assertEqual(
        ([h2_view], [h1_view], [h3_view]),
        issuedetailezt._GetBinnedHotlistViews([h1_view, h2_view, h3_view],
                                           involved_users=[111]))


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
