# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the issueentry servlet."""

import mox
import time
import unittest

from google.appengine.ext import testbed
import webapp2

from framework import framework_views
from framework import permissions
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issueentry


class IssueEntryTest(unittest.TestCase):
  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_taskqueue_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService(),
        features=fake.FeaturesService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    request = webapp2.Request.blank('/p/proj/issues/entry')
    response = webapp2.Response()
    self.servlet = issueentry.IssueEntry(
        request, response, services=self.services)
    self.user = self.services.user.TestAddUser('to_pass_tests', 0L)
    self.services.features.TestAddHotlist(
        name='dontcare', summary='', owner_ids=[0L])

    # Set-up for testing hotlist parsing.
    # Scenario:
    #   Users: U1, U2, and U3
    #   Hotlists:
    #     H1: owned by U1 (private)
    #     H2: owned by U2, can be edited by U1 (private)
    #     H2: owned by U3, can be edited by U1 and U2 (public)
    self.cnxn = fake.MonorailConnection()
    self.U1 = self.services.user.TestAddUser('U1', 111L)
    self.U2 = self.services.user.TestAddUser('U2', 222L)
    self.U3 = self.services.user.TestAddUser('U3', 333L)

    self.H1 = self.services.features.TestAddHotlist(
        name='H1', summary='', owner_ids=[111L], is_private=True)
    self.H2 = self.services.features.TestAddHotlist(
        name='H2', summary='', owner_ids=[222L], editor_ids=[111L],
        is_private=True)
    self.H2_U3 = self.services.features.TestAddHotlist(
        name='H2', summary='', owner_ids=[333L], editor_ids=[111L, 222L],
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

    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)
    self.mox.ReplayAll()

    page_data = self.servlet.GatherPageData(mr)
    self.mox.VerifyAll()
    self.assertEqual(page_data['initial_owner'], 'user@invalid')
    self.assertEqual(page_data['initial_status'], 'New')
    self.assertTrue(page_data['clear_summary_on_click'])
    self.assertTrue(page_data['must_edit_summary'])

  def testGatherPageData_DefaultOwnerAvailability(self):
    user = self.services.user.TestAddUser('user@invalid', 100)
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', services=self.services)
    mr.auth.user_view = framework_views.MakeUserView(
        'cnxn', self.services.user, 100)

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
    user = self.services.user.TestAddUser('user@invalid', 100)

    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)
    self.mox.ReplayAll()
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    self.services.config.StoreConfig(mr.cnxn, config)
    config.templates[1].summary_must_be_edited = False

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

  def testProcessFormData_RedirectToEnteredIssue(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry')
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    mr.perms = permissions.EMPTY_PERMISSIONSET
    post_data = fake.PostData(
        summary=['fake summary'],
        comment=['fake comment'],
        status=['New'])

    self.mox.StubOutWithMock(self.servlet, 'CheckCaptcha')
    self.servlet.CheckCaptcha(mr, mox.IgnoreArg())
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(mr, post_data)

    self.mox.VerifyAll()
    self.assertTrue('/p/proj/issues/detail?id=' in url)

  def testProcessFormData_RejectPlacedholderSummary(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry')
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    mr.perms = permissions.EMPTY_PERMISSIONSET
    post_data = fake.PostData(
        summary=[issueentry.PLACEHOLDER_SUMMARY],
        comment=['fake comment'],
        status=['New'])

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='', initial_comment='fake comment',
        initial_components='', initial_owner='', initial_status='New',
        initial_summary='Enter one-line summary', initial_hotlists='',
        labels=[])
    self.mox.ReplayAll()

    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Summary is required', mr.errors.summary)
    self.assertIsNone(url)

  def testProcessFormData_RejectUnmodifiedTemplate(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry')
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    template = config.templates[0]
    post_data = fake.PostData(
        summary=['Nya nya I modified the summary'],
        comment=[template.content],
        status=['New'])

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='', initial_comment=template.content,
        initial_components='', initial_owner='', initial_status='New',
        initial_summary='Nya nya I modified the summary', initial_hotlists='',
        labels=[])
    self.mox.ReplayAll()

    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Template must be filled out.', mr.errors.comment)
    self.assertIsNone(url)

  def test_SelectTemplate(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry')
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    templ = issueentry._SelectTemplate(None, config, False)
    self.assertEquals('Defect report from user', templ.name)

    templ = issueentry._SelectTemplate(None, config, True)
    self.assertEquals('Defect report from developer', templ.name)

  def testProcessFormData_RejectNonexistentHotlist(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', user_info={'user_id': 111L})
    entered_hotlists = 'H3'
    post_data = fake.PostData(hotlists=[entered_hotlists])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='', initial_comment='',
        initial_components='', initial_owner='', initial_status='',
        initial_summary='', initial_hotlists=entered_hotlists, labels=[])
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('You have no hotlist(s) named: H3', mr.errors.hotlists)
    self.assertIsNone(url)

  def testProcessFormData_RejectNonexistentHotlistOwner(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', user_info={'user_id': 111L})
    entered_hotlists = 'abc:H1'
    post_data = fake.PostData(hotlists=[entered_hotlists])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='', initial_comment='',
        initial_components='', initial_owner='', initial_status='',
        initial_summary='', initial_hotlists=entered_hotlists, labels=[])
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('You have no hotlist(s) owned by: abc', mr.errors.hotlists)
    self.assertIsNone(url)

  def testProcessFormData_RejectInvalidHotlistName(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/entry', user_info={'user_id': 111L})
    entered_hotlists = 'U1:H2'
    post_data = fake.PostData(hotlists=[entered_hotlists])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, component_required=None, fields=[], initial_blocked_on='',
        initial_blocking='', initial_cc='', initial_comment='',
        initial_components='', initial_owner='', initial_status='',
        initial_summary='', initial_hotlists=entered_hotlists, labels=[])
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Not in your hotlist(s): U1:H2', mr.errors.hotlists)
    self.assertIsNone(url)

  # TODO(aneeshm): add a test for the ambiguous hotlist name case; it works
  # correctly when tested locally, but for some reason doesn't in the test
  # environment. Probably a result of some quirk in fake.py?
