# -*- coding: utf-8 -*-
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for notify_helpers.py."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest
import os

from google.appengine.api import taskqueue
from google.appengine.ext import testbed

from features import notify_helpers
from features import notify_reasons
from framework import emailfmt
from framework import framework_views
from framework import urls
from proto import user_pb2
from services import service_manager
from testing import fake


REPLY_NOT_ALLOWED = notify_reasons.REPLY_NOT_ALLOWED
REPLY_MAY_COMMENT = notify_reasons.REPLY_MAY_COMMENT
REPLY_MAY_UPDATE = notify_reasons.REPLY_MAY_UPDATE


class TaskQueueingFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_taskqueue_stub()
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    self.taskqueue_stub._root_path = os.path.dirname(
        os.path.dirname(os.path.dirname( __file__ )))

  def tearDown(self):
    self.testbed.deactivate()

  def testAddAllEmailTasks(self):
    notify_helpers.AddAllEmailTasks(
      tasks=[{'to': 'user'}, {'to': 'user2'}])

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.OUTBOUND_EMAIL_TASK + '.do')
    self.assertEqual(2, len(tasks))


class MergeLinkedAccountReasonsTest(unittest.TestCase):

  def setUp(self):
    parent = user_pb2.User(
        user_id=111, email='parent@example.org',
        linked_child_ids=[222])
    child = user_pb2.User(
        user_id=222, email='child@example.org',
        linked_parent_id=111)
    user_3 = user_pb2.User(
        user_id=333, email='user4@example.org')
    user_4 = user_pb2.User(
        user_id=444, email='user4@example.org')
    self.addr_perm_parent = notify_reasons.AddrPerm(
        False, parent.email, parent, notify_reasons.REPLY_NOT_ALLOWED,
        user_pb2.UserPrefs())
    self.addr_perm_child = notify_reasons.AddrPerm(
        False, child.email, child, notify_reasons.REPLY_NOT_ALLOWED,
        user_pb2.UserPrefs())
    self.addr_perm_3 = notify_reasons.AddrPerm(
        False, user_3.email, user_3, notify_reasons.REPLY_NOT_ALLOWED,
        user_pb2.UserPrefs())
    self.addr_perm_4 = notify_reasons.AddrPerm(
        False, user_4.email, user_4, notify_reasons.REPLY_NOT_ALLOWED,
        user_pb2.UserPrefs())
    self.addr_perm_5 = notify_reasons.AddrPerm(
        False, 'alias@example.com', None, notify_reasons.REPLY_NOT_ALLOWED,
        user_pb2.UserPrefs())

  def testEmptyDict(self):
    """Zero users to notify."""
    self.assertEqual(
        {},
        notify_helpers._MergeLinkedAccountReasons({}, {}))

  def testNormal(self):
    """No users are related."""
    addr_to_addrperm = {
       self.addr_perm_parent.address: self.addr_perm_parent,
       self.addr_perm_3.address: self.addr_perm_3,
       self.addr_perm_4.address: self.addr_perm_4,
       self.addr_perm_5.address: self.addr_perm_5,
       }
    addr_to_reasons = {
       self.addr_perm_parent.address: [notify_reasons.REASON_CCD],
       self.addr_perm_3.address: [notify_reasons.REASON_OWNER],
       self.addr_perm_4.address: [notify_reasons.REASON_CCD],
       self.addr_perm_5.address: [notify_reasons.REASON_CCD],
       }
    self.assertEqual(
        {self.addr_perm_parent.address: [notify_reasons.REASON_CCD],
         self.addr_perm_3.address: [notify_reasons.REASON_OWNER],
         self.addr_perm_4.address: [notify_reasons.REASON_CCD],
         self.addr_perm_5.address: [notify_reasons.REASON_CCD]
         },
        notify_helpers._MergeLinkedAccountReasons(
            addr_to_addrperm, addr_to_reasons))

  def testMerged(self):
    """A child is merged into parent notification."""
    addr_to_addrperm = {
       self.addr_perm_parent.address: self.addr_perm_parent,
       self.addr_perm_child.address: self.addr_perm_child,
       }
    addr_to_reasons = {
       self.addr_perm_parent.address: [notify_reasons.REASON_OWNER],
       self.addr_perm_child.address: [notify_reasons.REASON_CCD],
       }
    self.assertEqual(
        {self.addr_perm_parent.address:
         [notify_reasons.REASON_OWNER,
          notify_reasons.REASON_LINKED_ACCOUNT]
         },
        notify_helpers._MergeLinkedAccountReasons(
            addr_to_addrperm, addr_to_reasons))


class MakeBulletedEmailWorkItemsTest(unittest.TestCase):

  def setUp(self):
    self.project = fake.Project(project_name='proj1')
    self.commenter_view = framework_views.StuffUserView(
        111, 'test@example.com', True)
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1234, 'summary', 'New', 111)
    self.detail_url = 'http://test-detail-url.com/id=1234'

  def testEmptyAddrs(self):
    """Test the case where we found zero users to notify."""
    email_tasks = notify_helpers.MakeBulletedEmailWorkItems(
        [], self.issue, 'link only body', 'non-member body', 'member body',
        self.project, 'example.com',
        self.commenter_view, self.detail_url)
    self.assertEqual([], email_tasks)
    email_tasks = notify_helpers.MakeBulletedEmailWorkItems(
        [([], 'reason')], self.issue, 'link only body', 'non-member body',
        'member body', self.project,
        'example.com', self.commenter_view, self.detail_url)
    self.assertEqual([], email_tasks)


class LinkOnlyLogicTest(unittest.TestCase):

  def setUp(self):
    self.user_prefs = user_pb2.UserPrefs()
    self.user = user_pb2.User()
    self.issue = fake.MakeTestIssue(
        789, 1, 'summary one', 'New', 111)
    self.rvg_issue = fake.MakeTestIssue(
        789, 2, 'summary two', 'New', 111, labels=['Restrict-View-Google'])
    self.more_restricted_issue = fake.MakeTestIssue(
        789, 3, 'summary three', 'New', 111, labels=['Restrict-View-Core'])
    self.both_restricted_issue = fake.MakeTestIssue(
        789, 4, 'summary four', 'New', 111,
        labels=['Restrict-View-Google', 'Restrict-View-Core'])
    self.addr_perm = notify_reasons.AddrPerm(
        False, 'user@example.com', self.user, notify_reasons.REPLY_MAY_COMMENT,
        self.user_prefs)

  def testGetNotifyRestrictedIssues_PrefIsSet(self):
    """When the notify_restricted_issues pref is set, we use it."""
    self.user_prefs.prefs.extend([
        user_pb2.UserPrefValue(name='x', value='y'),
        user_pb2.UserPrefValue(name='notify_restricted_issues', value='z'),
        ])
    actual = notify_helpers._GetNotifyRestrictedIssues(
        self.user_prefs, 'user@example.com', self.user)
    self.assertEqual('z', actual)

  def testGetNotifyRestrictedIssues_UserHasVisited(self):
    """If user has ever visited, we know that they are not a mailing list."""
    self.user.last_visit_timestamp = 123456789
    actual = notify_helpers._GetNotifyRestrictedIssues(
        self.user_prefs, 'user@example.com', self.user)
    self.assertEqual('notify with details', actual)

  def testGetNotifyRestrictedIssues_GooglerNeverVisited(self):
    """It could be a noogler or google mailing list."""
    actual = notify_helpers._GetNotifyRestrictedIssues(
        self.user_prefs, 'user@google.com', self.user)
    self.assertEqual('notify with details: Google', actual)

  def testGetNotifyRestrictedIssues_NonGooglerNeverVisited(self):
    """It could be a new non-noogler or public mailing list."""
    actual = notify_helpers._GetNotifyRestrictedIssues(
        self.user_prefs, 'user@example.com', self.user)
    self.assertEqual('notify with link only', actual)

    # If email does not match any known user, user object will be None.
    actual = notify_helpers._GetNotifyRestrictedIssues(
        self.user_prefs, 'user@example.com', None)
    self.assertEqual('notify with link only', actual)

  def testShouldUseLinkOnly_UnrestrictedIssue(self):
    """Issue is not restricted, so go ahead and send comment details."""
    self.assertFalse(notify_helpers._ShouldUseLinkOnly(
        self.addr_perm, self.issue))

  @mock.patch('features.notify_helpers._GetNotifyRestrictedIssues')
  def testShouldUseLinkOnly_NotifyWithDetails(self, fake_gnri):
    """Issue is restricted, and user is allowed to get full comment details."""
    fake_gnri.return_value = notify_helpers.NOTIFY_WITH_DETAILS
    self.assertFalse(notify_helpers._ShouldUseLinkOnly(
        self.addr_perm, self.rvg_issue))
    self.assertFalse(notify_helpers._ShouldUseLinkOnly(
        self.addr_perm, self.more_restricted_issue))
    self.assertFalse(notify_helpers._ShouldUseLinkOnly(
        self.addr_perm, self.both_restricted_issue))


class MakeEmailWorkItemTest(unittest.TestCase):

  def setUp(self):
    self.project = fake.Project(project_name='proj1')
    self.project.process_inbound_email = True
    self.commenter_view = framework_views.StuffUserView(
        111, 'test@example.com', True)
    self.expected_html_footer = (
        'You received this message because:<br/>  1. reason<br/><br/>You may '
        'adjust your notification preferences at:<br/><a href="https://'
        'example.com/hosting/settings">https://example.com/hosting/settings'
        '</a>')
    self.services = service_manager.Services(
        user=fake.UserService())
    self.member = self.services.user.TestAddUser('member@example.com', 222)
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1234, 'summary', 'New', 111,
        project_name='proj1')
    self.detail_url = 'http://test-detail-url.com/id=1234'

  @mock.patch('features.notify_helpers._ShouldUseLinkOnly')
  def testBodySelection_LinkOnly(self, mock_sulo):
    """We send a link-only body when _ShouldUseLinkOnly() is true."""
    mock_sulo.return_value = True
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            True, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'body mem', 'body mem', self.project,
        'example.com', self.commenter_view, self.detail_url)
    self.assertIn('body link-only', email_task['body'])

  def testBodySelection_Member(self):
    """We send members the email body that is indented for members."""
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            True, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'body mem', 'body mem', self.project,
        'example.com', self.commenter_view, self.detail_url)
    self.assertIn('body mem', email_task['body'])

  def testBodySelection_NonMember(self):
    """We send non-members the email body that is indented for non-members."""
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            False, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'body non', 'body mem', self.project,
        'example.com', self.commenter_view, self.detail_url)

    self.assertEqual('a@a.com', email_task['to'])
    self.assertEqual('Issue 1234 in proj1: summary', email_task['subject'])
    self.assertIn('body non', email_task['body'])
    self.assertEqual(
      emailfmt.FormatFromAddr(self.project, commenter_view=self.commenter_view,
                              can_reply_to=False),
      email_task['from_addr'])
    self.assertEqual(emailfmt.NoReplyAddress(), email_task['reply_to'])

  def testHtmlBody(self):
    """"An html body is sent if a detail_url is specified."""
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            False, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'body non', 'body mem', self.project,
        'example.com', self.commenter_view, self.detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': self.detail_url,
            'body': 'body non-- <br/>%s' % self.expected_html_footer})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_WithUnicodeChars(self):
    """"An html body is sent if a detail_url is specified."""
    unicode_content = '\xe2\x9d\xa4     â    â'
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            False, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', unicode_content, 'unused body mem',
        self.project, 'example.com', self.commenter_view, self.detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': self.detail_url,
            'body': '%s-- <br/>%s' % (unicode_content.decode('utf-8'),
                                      self.expected_html_footer)})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_WithLinks(self):
    """"An html body is sent if a detail_url is specified."""
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            False, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'test google.com test', 'unused body mem',
        self.project, 'example.com', self.commenter_view, self.detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': self.detail_url,
            'body': (
            'test <a href="http://google.com">google.com</a> test-- <br/>%s' % (
                self.expected_html_footer))})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_LinkWithinTags(self):
    """"An html body is sent with correct <a href>s."""
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            False, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'a <http://google.com> z', 'unused body',
        self.project, 'example.com', self.commenter_view,
        self.detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': self.detail_url,
            'body': (
                'a &lt;<a href="http://google.com">http://google.com</a>&gt; '
                'z-- <br/>%s' % self.expected_html_footer)})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_EmailWithinTags(self):
    """"An html body is sent with correct <a href>s."""
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            False, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'a <tt@chromium.org> <aa@chromium.org> z',
        'unused body mem', self.project, 'example.com', self.commenter_view,
        self.detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': self.detail_url,
            'body': (
                'a &lt;<a href="mailto:tt@chromium.org">tt@chromium.org</a>&gt;'
                ' &lt;<a href="mailto:aa@chromium.org">aa@chromium.org</a>&gt; '
                'z-- <br/>%s' % self.expected_html_footer)})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_WithEscapedHtml(self):
    """"An html body is sent with html content escaped."""
    body_with_html_content = (
        '<a href="http://www.google.com">test</a> \'something\'')
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            False, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', body_with_html_content, 'unused body mem',
        self.project, 'example.com', self.commenter_view, self.detail_url)

    escaped_body_with_html_content = (
        '&lt;a href=&quot;http://www.google.com&quot;&gt;test&lt;/a&gt; '
        '&#39;something&#39;')
    notify_helpers._MakeNotificationFooter(
        ['reason'], REPLY_NOT_ALLOWED, 'example.com')
    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': self.detail_url,
            'body': '%s-- <br/>%s' % (escaped_body_with_html_content,
                                      self.expected_html_footer)})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def doTestAddHTMLTags(self, body, expected):
    actual = notify_helpers._AddHTMLTags(body)
    self.assertEqual(expected, actual)

  def testAddHTMLTags_Email(self):
    """An email address produces <a href="mailto:...">...</a>."""
    self.doTestAddHTMLTags(
      'test test@example.com.',
      ('test <a href="mailto:test@example.com">'
       'test@example.com</a>.'))

  def testAddHTMLTags_EmailInQuotes(self):
    """Quoted "test@example.com" produces "<a href="...">...</a>"."""
    self.doTestAddHTMLTags(
      'test "test@example.com".',
      ('test &quot;<a href="mailto:test@example.com">'
       'test@example.com</a>&quot;.'))

  def testAddHTMLTags_EmailInAngles(self):
    """Bracketed <test@example.com> produces &lt;<a href="...">...</a>&gt;."""
    self.doTestAddHTMLTags(
      'test <test@example.com>.',
      ('test &lt;<a href="mailto:test@example.com">'
       'test@example.com</a>&gt;.'))

  def testAddHTMLTags_Website(self):
    """A website URL produces <a href="http:...">...</a>."""
    self.doTestAddHTMLTags(
      'test http://www.example.com.',
      ('test <a href="http://www.example.com">'
       'http://www.example.com</a>.'))

  def testAddHTMLTags_WebsiteInQuotes(self):
    """A link in quotes gets the quotes escaped."""
    self.doTestAddHTMLTags(
      'test "http://www.example.com".',
      ('test &quot;<a href="http://www.example.com">'
       'http://www.example.com</a>&quot;.'))

  def testAddHTMLTags_WebsiteInAngles(self):
    """Bracketed <www.example.com> produces &lt;<a href="...">...</a>&gt;."""
    self.doTestAddHTMLTags(
      'test <http://www.example.com>.',
      ('test &lt;<a href="http://www.example.com">'
       'http://www.example.com</a>&gt;.'))

  def testReplyInvitation(self):
    """We include a footer about replying that is appropriate for that user."""
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            True, 'a@a.com', self.member, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'body non', 'body mem', self.project,
        'example.com', self.commenter_view, self.detail_url)
    self.assertEqual(emailfmt.NoReplyAddress(), email_task['reply_to'])
    self.assertNotIn('Reply to this email', email_task['body'])

    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            True, 'a@a.com', self.member, REPLY_MAY_COMMENT,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'body non', 'body mem', self.project,
        'example.com', self.commenter_view, self.detail_url)
    self.assertEqual(
      '%s@%s' % (self.project.project_name, emailfmt.MailDomain()),
      email_task['reply_to'])
    self.assertIn('Reply to this email to add a comment', email_task['body'])
    self.assertNotIn('make changes', email_task['body'])

    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            True, 'a@a.com', self.member, REPLY_MAY_UPDATE,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'body non', 'body mem', self.project,
        'example.com', self.commenter_view, self.detail_url)
    self.assertEqual(
      '%s@%s' % (self.project.project_name, emailfmt.MailDomain()),
      email_task['reply_to'])
    self.assertIn('Reply to this email to add a comment', email_task['body'])
    self.assertIn('make updates', email_task['body'])

  def testInboundEmailDisabled(self):
    """We don't invite replies if they are disabled for this project."""
    self.project.process_inbound_email = False
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            True, 'a@a.com', self.member, REPLY_MAY_UPDATE,
            user_pb2.UserPrefs()),
        ['reason'], self.issue,
        'body link-only', 'body non', 'body mem',
        self.project, 'example.com', self.commenter_view, self.detail_url)
    self.assertEqual(emailfmt.NoReplyAddress(), email_task['reply_to'])

  def testReasons(self):
    """The footer lists reasons why that email was sent to that user."""
    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            True, 'a@a.com', self.member, REPLY_MAY_UPDATE,
            user_pb2.UserPrefs()),
        ['Funny', 'Caring', 'Near'], self.issue,
        'body link-only', 'body non', 'body mem',
        self.project, 'example.com', self.commenter_view, self.detail_url)
    self.assertIn('because:', email_task['body'])
    self.assertIn('1. Funny', email_task['body'])
    self.assertIn('2. Caring', email_task['body'])
    self.assertIn('3. Near', email_task['body'])

    email_task = notify_helpers._MakeEmailWorkItem(
        notify_reasons.AddrPerm(
            True, 'a@a.com', self.member, REPLY_MAY_UPDATE,
            user_pb2.UserPrefs()),
        [], self.issue,
        'body link-only', 'body non', 'body mem',
        self.project, 'example.com', self.commenter_view, self.detail_url)
    self.assertNotIn('because', email_task['body'])


class MakeNotificationFooterTest(unittest.TestCase):

  def testMakeNotificationFooter_NoReason(self):
    footer = notify_helpers._MakeNotificationFooter(
        [], REPLY_NOT_ALLOWED, 'example.com')
    self.assertEqual('', footer)

  def testMakeNotificationFooter_WithReason(self):
    footer = notify_helpers._MakeNotificationFooter(
        ['REASON'], REPLY_NOT_ALLOWED, 'example.com')
    self.assertIn('REASON', footer)
    self.assertIn('https://example.com/hosting/settings', footer)

    footer = notify_helpers._MakeNotificationFooter(
        ['REASON'], REPLY_NOT_ALLOWED, 'example.com')
    self.assertIn('REASON', footer)
    self.assertIn('https://example.com/hosting/settings', footer)

  def testMakeNotificationFooter_ManyReasons(self):
    footer = notify_helpers._MakeNotificationFooter(
        ['Funny', 'Caring', 'Warmblooded'], REPLY_NOT_ALLOWED,
        'example.com')
    self.assertIn('Funny', footer)
    self.assertIn('Caring', footer)
    self.assertIn('Warmblooded', footer)

  def testMakeNotificationFooter_WithReplyInstructions(self):
    footer = notify_helpers._MakeNotificationFooter(
        ['REASON'], REPLY_NOT_ALLOWED, 'example.com')
    self.assertNotIn('Reply', footer)
    self.assertIn('https://example.com/hosting/settings', footer)

    footer = notify_helpers._MakeNotificationFooter(
        ['REASON'], REPLY_MAY_COMMENT, 'example.com')
    self.assertIn('add a comment', footer)
    self.assertNotIn('make updates', footer)
    self.assertIn('https://example.com/hosting/settings', footer)

    footer = notify_helpers._MakeNotificationFooter(
        ['REASON'], REPLY_MAY_UPDATE, 'example.com')
    self.assertIn('add a comment', footer)
    self.assertIn('make updates', footer)
    self.assertIn('https://example.com/hosting/settings', footer)
