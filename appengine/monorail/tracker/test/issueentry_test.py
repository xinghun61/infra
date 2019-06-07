# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the issueentry servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mox
import os
import time
import unittest

from third_party import ezt

from google.appengine.ext import testbed
from mock import Mock, patch
import webapp2

from framework import framework_bizobj
from framework import framework_views
from framework import permissions
from services import service_manager
from services import template_svc
from testing import fake
from testing import testing_helpers
from tracker import issueentry
from tracker import tracker_bizobj
from proto import tracker_pb2
from proto import user_pb2


class IssueEntryTest(unittest.TestCase):
  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_taskqueue_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    # Load queue.yaml.
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    self.taskqueue_stub._root_path = os.path.dirname(
        os.path.dirname(os.path.dirname( __file__ )))

    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        template=Mock(spec=template_svc.TemplateService),
        features=fake.FeaturesService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    request = webapp2.Request.blank('/p/proj/issues/entry')
    response = webapp2.Response()
    self.servlet = issueentry.IssueEntry(
        request, response, services=self.services)
    self.user = self.services.user.TestAddUser('to_pass_tests', 0L)
    self.services.features.TestAddHotlist(
        name='dontcare', summary='', owner_ids=[0L])
    self.template = testing_helpers.DefaultTemplates()[1]
    self.services.template.GetTemplateByName = Mock(return_value=self.template)
    self.services.template.GetTemplateSetForProject = Mock(
        return_value=[(1, 'name', False)])

    # Set-up for testing hotlist parsing.
    # Scenario:
    #   Users: U1, U2, and U3
    #   Hotlists:
    #     H1: owned by U1 (private)
    #     H2: owned by U2, can be edited by U1 (private)
    #     H2: owned by U3, can be edited by U1 and U2 (public)
    self.cnxn = fake.MonorailConnection()
    self.U1 = self.services.user.TestAddUser('U1', 111)
    self.U2 = self.services.user.TestAddUser('U2', 222)
    self.U3 = self.services.user.TestAddUser('U3', 333)

    self.H1 = self.services.features.TestAddHotlist(
        name='H1', summary='', owner_ids=[111], is_private=True)
    self.H2 = self.services.features.TestAddHotlist(
        name='H2', summary='', owner_ids=[222], editor_ids=[111],
        is_private=True)
    self.H2_U3 = self.services.features.TestAddHotlist(
        name='H2', summary='', owner_ids=[333], editor_ids=[111, 222],
        is_private=False)

    self.mox = mox.Mox()

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testAssertBasePermission(self):
    """Permit users with CREATE_ISSUE."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services,
        perms=permissions.EMPTY_PERMISSIONSET)
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    self.servlet.AssertBasePermission(mr)

  def testDiscardUnusedTemplateLabelPrefixes(self):
    labels = ['pre-val', 'other-value', 'oneword', 'x', '-y', '-w-z', '', '-']
    self.assertEqual(labels,
                     issueentry._DiscardUnusedTemplateLabelPrefixes(labels))

    labels = ['prefix-value', 'other-?', 'third-', '', '-', '-?']
    self.assertEqual(['prefix-value', 'third-', '', '-'],
                     issueentry._DiscardUnusedTemplateLabelPrefixes(labels))

  def testGatherPageData(self):
    user = self.services.user.TestAddUser('user@invalid', 100)
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.MakeUserView(
        'cnxn', self.services.user, 100)
    mr.template_name = 'rutabaga'

    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)
    self.mox.ReplayAll()
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    config.field_defs = [
        tracker_bizobj.MakeFieldDef(
            24, mr.project_id, 'NotEnum',
            tracker_pb2.FieldTypes.STR_TYPE, None, '', False, False,
            False, None, None, '', False, '', '',
            tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False),
        tracker_bizobj.MakeFieldDef(
            24, mr.project_id, 'Choices',
            tracker_pb2.FieldTypes.ENUM_TYPE, None, '', False, False,
            False, None, None, '', False, '', '',
            tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)]
    self.services.config.StoreConfig(mr.cnxn, config)
    template = tracker_pb2.TemplateDef(
        labels=['NotEnum-Not-Masked', 'Choices-Masked'])
    self.services.template.GetTemplateByName.return_value = template

    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()
    self.assertEqual(page_data['initial_owner'], 'user@invalid')
    self.assertEqual(page_data['initial_status'], 'New')
    self.assertTrue(page_data['clear_summary_on_click'])
    self.assertTrue(page_data['must_edit_summary'])
    self.assertEqual(page_data['labels'], ['NotEnum-Not-Masked'])

  def testGatherPageData_Approvals(self):
    user = self.services.user.TestAddUser('user@invalid', 100)
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.MakeUserView(
        'cnxn', self.services.user, 100)
    mr.template_name = 'rutabaga'

    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)
    self.mox.ReplayAll()
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    config.field_defs = [
    tracker_bizobj.MakeFieldDef(
        24, mr.project_id, 'UXReview',
        tracker_pb2.FieldTypes.APPROVAL_TYPE, None, '', False, False,
        False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)]
    self.services.config.StoreConfig(mr.cnxn, config)
    template = tracker_pb2.TemplateDef()
    template.phases = [tracker_pb2.Phase(
        phase_id=1, rank=4, name='Stable')]
    template.approval_values = [tracker_pb2.ApprovalValue(
        approval_id=24, phase_id=1,
        status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)]
    self.services.template.GetTemplateByName.return_value = template

    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()
    self.assertEqual(page_data['approvals'][0].field_name, 'UXReview')
    self.assertEqual(page_data['initial_phases'][0],
                          tracker_pb2.Phase(phase_id=1, name='Stable', rank=4))
    self.assertEqual(page_data['prechecked_approvals'], ['24_phase_0'])
    self.assertEqual(page_data['required_approval_ids'], [24])

    # phase fields row shown when config contains phase fields.
    config.field_defs.append(tracker_bizobj.MakeFieldDef(
        26, mr.project_id, 'GateTarget',
        tracker_pb2.FieldTypes.INT_TYPE, None, '', False, False, False,
        None, None, '', False, '', '', tracker_pb2.NotifyTriggers.NEVER,
        'no_action', 'doc', False, is_phase_field=True))
    self.services.config.StoreConfig(mr.cnxn, config)
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(page_data['issue_phase_names'], ['stable'])

    # approval subfields in config hidden when chosen template does not contain
    # its parent approval
    template = tracker_pb2.TemplateDef()
    self.services.template.GetTemplateByName.return_value = template
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(page_data['approvals'], [])
    # phase fields row hidden when template has no phases
    self.assertEqual(page_data['issue_phase_names'], [])

  def testGatherPageData_DefaultOwnerAvailability(self):
    user = self.services.user.TestAddUser('user@invalid', 100)
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.MakeUserView(
        'cnxn', self.services.user, 100)
    mr.template_name = 'rutabaga'

    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)
    self.mox.ReplayAll()

    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()
    self.assertEqual(page_data['initial_owner'], 'user@invalid')
    self.assertEqual(page_data['owner_avail_state'], 'never')
    self.assertEqual(
        page_data['owner_avail_message_short'],
        'User never visited')

    user.last_visit_timestamp = int(time.time())
    mr.auth.user_view = framework_views.MakeUserView(
        'cnxn', self.services.user, 100)
    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()
    self.assertEqual(page_data['initial_owner'], 'user@invalid')
    self.assertEqual(page_data['owner_avail_state'], None)
    self.assertEqual(page_data['owner_avail_message_short'], '')

  def testGatherPageData_TemplateAllowsKeepingSummary(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    mr.template_name = 'rutabaga'
    user = self.services.user.TestAddUser('user@invalid', 100)

    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)
    self.mox.ReplayAll()
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    self.services.config.StoreConfig(mr.cnxn, config)
    self.template.summary_must_be_edited = False

    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()
    self.assertEqual(page_data['initial_owner'], 'user@invalid')
    self.assertEqual(page_data['initial_status'], 'New')
    self.assertFalse(page_data['clear_summary_on_click'])
    self.assertFalse(page_data['must_edit_summary'])

  def testGatherPageData_DeepLinkSetsSummary(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry?summary=foo', services=self.services)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    user = self.services.user.TestAddUser('user@invalid', 100)
    mr.template_name = 'rutabaga'

    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)
    self.mox.ReplayAll()

    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()
    self.assertEqual(page_data['initial_owner'], 'user@invalid')
    self.assertEqual(page_data['initial_status'], 'New')
    self.assertFalse(page_data['clear_summary_on_click'])
    self.assertTrue(page_data['must_edit_summary'])

  @patch('framework.framework_bizobj.UserIsInProject')
  def testGatherPageData_MembersOnlyTemplatesExcluded(self,
        mockUserIsInProject):
    """Templates with members_only=True are excluded from results
    when the user is not a member of the project."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    user = self.services.user.TestAddUser('user@invalid', 100)
    mr.template_name = 'rutabaga'
    self.services.template.GetTemplateSetForProject = Mock(
        return_value=[(1, 'one', False), (2, 'two', True)])
    mockUserIsInProject.return_value = False

    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)
    self.mox.ReplayAll()

    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()
    self.assertEqual(page_data['config'].template_names, ['one'])

  @patch('framework.framework_bizobj.UserIsInProject')
  def testGatherPageData_DefaultTemplatesMember(self, mockUserIsInProject):
    """If no template is specified, the default one is used based on
    whether the user is a project member."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    user = self.services.user.TestAddUser('user@invalid', 100)
    self.services.template.GetTemplateSetForProject = Mock(
        return_value=[(1, 'one', False), (2, 'two', True)])
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    config.default_template_for_users = 456
    config.default_template_for_developers = 789
    self.services.config.StoreConfig(mr.cnxn, config)

    mockUserIsInProject.return_value = True
    self.services.template.GetTemplateById = Mock(return_value=self.template)
    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)

    self.mox.ReplayAll()
    self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()

    call_args = self.services.template.GetTemplateById.call_args[0]
    self.assertEqual(call_args[1], 789)

  @patch('framework.framework_bizobj.UserIsInProject')
  def testGatherPageData_DefaultTemplatesNonMember(self, mockUserIsInProject):
    """If no template is specified, the default one is used based on
    whether the user is not a project member."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    user = self.services.user.TestAddUser('user@invalid', 100)
    self.services.template.GetTemplateSetForProject = Mock(
        return_value=[(1, 'one', False), (2, 'two', True)])
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    config.default_template_for_users = 456
    config.default_template_for_developers = 789
    self.services.config.StoreConfig(mr.cnxn, config)

    mockUserIsInProject.return_value = False
    self.services.template.GetTemplateById = Mock(return_value=self.template)
    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)

    self.mox.ReplayAll()
    self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()

    call_args = self.services.template.GetTemplateById.call_args[0]
    self.assertEqual(call_args[1], 456)

  def testGatherPageData_MissingDefaultTemplates(self):
    """If the default templates were deleted, pick the first template."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    user = self.services.user.TestAddUser('user@invalid', 100)
    self.services.template.GetTemplateSetForProject = Mock(
        return_value=[(1, 'one', False), (2, 'two', True)])

    self.services.template.GetTemplateById.return_value = None
    self.services.template.GetProjectTemplates.return_value = [
        tracker_pb2.TemplateDef(members_only=True),
        tracker_pb2.TemplateDef(members_only=False)]
    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)

    self.mox.ReplayAll()
    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()

    self.assertTrue(self.services.template.GetProjectTemplates.called)
    self.assertTrue(page_data['config'].template_view.members_only)

  def testGatherPageData_IncorrectTemplate(self):
    """The handler shouldn't error out if passed a non-existent template."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    mr.template_name = 'rutabaga'

    user = self.services.user.TestAddUser('user@invalid', 100)
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    config.default_template_for_users = 456
    config.default_template_for_developers = 789
    self.services.config.StoreConfig(mr.cnxn, config)

    self.services.template.GetTemplateSetForProject.return_value = [
        (1, 'one', False), (2, 'two', True)]
    self.services.template.GetTemplateByName.return_value = None
    self.services.template.GetTemplateById.return_value = \
        tracker_pb2.TemplateDef(template_id=123, labels=['yo'])
    self.services.template.GetProjectTemplates.return_value = [
        tracker_pb2.TemplateDef(labels=['no']),
        tracker_pb2.TemplateDef(labels=['maybe'])]
    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)

    self.mox.ReplayAll()
    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()

    self.assertTrue(self.services.template.GetTemplateByName.called)
    self.assertTrue(self.services.template.GetTemplateById.called)
    self.assertFalse(self.services.template.GetProjectTemplates.called)
    self.assertEqual(page_data['config'].template_view.label0, 'yo')

  def testGatherPageData_RestrictNewIssues(self):
    """Users with this pref set default to reporting issues with R-V-G."""
    self.mox.ReplayAll()
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    user = self.services.user.TestAddUser('user@invalid', 100)
    self.services.user.GetUser = Mock(return_value=user)
    self.services.template.GetTemplateById = Mock(return_value=self.template)

    mr.auth.user_id = 100
    page_data = self.servlet.GatherPageData(mr)
    self.assertNotIn('Restrict-View-Google', page_data['labels'])

    pref = user_pb2.UserPrefValue(name='restrict_new_issues', value='true')
    self.services.user.SetUserPrefs(self.cnxn, 100, [pref])
    page_data = self.servlet.GatherPageData(mr)
    self.assertIn('Restrict-View-Google', page_data['labels'])

  def testGatherHelpData_Anon(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', project=self.project)
    mr.auth.user_pb = user_pb2.User()
    mr.auth.user_id = 0

    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(
        {'account_cue': None,
         'cue': None,
         'is_privileged_domain_user': None},
        help_data)

  def testGatherHelpData_NewUser(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', project=self.project)
    mr.auth.user_pb = user_pb2.User(user_id=111)
    mr.auth.user_id = 111

    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(
        {'account_cue': None,
         'cue': 'privacy_click_through',
         'is_privileged_domain_user': None},
        help_data)

  def testGatherHelpData_AlreadyClickedThroughPrivacy(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', project=self.project)
    mr.auth.user_pb = user_pb2.User(user_id=111)
    mr.auth.user_id = 111
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='privacy_click_through', value='true')])

    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(
        {'account_cue': None,
         'cue': 'code_of_conduct',
         'is_privileged_domain_user': None},
        help_data)

  def testGatherHelpData_DismissedEverything(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', project=self.project)
    mr.auth.user_pb = user_pb2.User(user_id=111)
    mr.auth.user_id = 111
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='privacy_click_through', value='true'),
         user_pb2.UserPrefValue(name='code_of_conduct', value='true')])

    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(
        {'account_cue': None,
         'cue': None,
         'is_privileged_domain_user': None},
        help_data)

  def testProcessFormData_RedirectToEnteredIssue(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', project=self.project)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    mr.template_name = 'rutabaga'
    mr.auth.effective_ids = set([100])
    post_data = fake.PostData(
        template_name=['rutabaga'],
        summary=['fake summary'],
        comment=['fake comment'],
        status=['New'])

    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(mr, post_data)

    self.mox.VerifyAll()
    self.assertTrue('/p/proj/issues/detail?id=' in url)

  def testProcessFormData_RejectPlacedholderSummary(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry')
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    mr.perms = permissions.USER_PERMISSIONSET
    mr.template_name = 'rutabaga'
    post_data = fake.PostData(
        template_name=['rutabaga'],
        summary=[issueentry.PLACEHOLDER_SUMMARY],
        comment=['fake comment'],
        status=['New'])

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='', initial_comment='fake comment',
        initial_components='', initial_owner='', initial_status='New',
        initial_summary='Enter one-line summary', initial_hotlists='',
        labels=[], template_name='rutabaga')
    self.mox.ReplayAll()

    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Summary is required', mr.errors.summary)
    self.assertIsNone(url)

  def testProcessFormData_RejectUnmodifiedTemplate(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry')
    mr.perms = permissions.USER_PERMISSIONSET
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    post_data = fake.PostData(
        template_name=['rutabaga'],
        summary=['Nya nya I modified the summary'],
        comment=[self.template.content],
        status=['New'])

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='',
        initial_comment=self.template.content, initial_components='',
        initial_owner='', initial_status='New',
        initial_summary='Nya nya I modified the summary', initial_hotlists='',
        labels=[], template_name='rutabaga')
    self.mox.ReplayAll()

    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Template must be filled out.', mr.errors.comment)
    self.assertIsNone(url)

  def testProcessFormData_RejectNonexistentHotlist(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', user_info={'user_id': 111})
    entered_hotlists = 'H3'
    post_data = fake.PostData(hotlists=[entered_hotlists],
        template_name=['rutabaga'])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='', initial_comment='',
        initial_components='', initial_owner='', initial_status='',
        initial_summary='', initial_hotlists=entered_hotlists, labels=[],
        template_name='rutabaga')
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('You have no hotlist(s) named: H3', mr.errors.hotlists)
    self.assertIsNone(url)

  def testProcessFormData_RejectNonexistentHotlistOwner(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', user_info={'user_id': 111})
    entered_hotlists = 'abc:H1'
    post_data = fake.PostData(hotlists=[entered_hotlists],
                              template_name=['rutabaga'])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='', initial_comment='',
        initial_components='', initial_owner='', initial_status='',
        initial_summary='', initial_hotlists=entered_hotlists, labels=[],
        template_name='rutabaga')
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('You have no hotlist(s) owned by: abc', mr.errors.hotlists)
    self.assertIsNone(url)

  def testProcessFormData_RejectInvalidHotlistName(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', user_info={'user_id': 111})
    entered_hotlists = 'U1:H2'
    post_data = fake.PostData(hotlists=[entered_hotlists],
                              template_name=['rutabaga'])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='', initial_comment='',
        initial_components='', initial_owner='', initial_status='',
        initial_summary='', initial_hotlists=entered_hotlists, labels=[],
        template_name='rutabaga')
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Not in your hotlist(s): U1:H2', mr.errors.hotlists)
    self.assertIsNone(url)

  def testProcessFormData_TemplateNameMissing(self):
    """POST doesn't fail if no template_name is passed."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', project=self.project)
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    mr.auth.effective_ids = set([100])

    self.services.template.GetTemplateById.return_value = None
    self.services.template.GetProjectTemplates.return_value = [
        tracker_pb2.TemplateDef(members_only=True, content=''),
        tracker_pb2.TemplateDef(members_only=False, content='')]
    post_data = fake.PostData(
        summary=['fake summary'],
        comment=['fake comment'],
        status=['New'])

    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(mr, post_data)

    self.mox.VerifyAll()
    self.assertTrue('/p/proj/issues/detail?id=' in url)

  def testAttachDefaultApprovers(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.approval_defs = [
        tracker_pb2.ApprovalDef(
            approval_id=23, approver_ids=[222], survey='Question?'),
        tracker_pb2.ApprovalDef(
            approval_id=24, approver_ids=[111], survey='Question?')]
    approval_values = [tracker_pb2.ApprovalValue(
         approval_id=24, phase_id=1,
         status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)]
    issueentry._AttachDefaultApprovers(config, approval_values)
    self.assertEqual(approval_values[0].approver_ids, [111])

  # TODO(aneeshm): add a test for the ambiguous hotlist name case; it works
  # correctly when tested locally, but for some reason doesn't in the test
  # environment. Probably a result of some quirk in fake.py?
