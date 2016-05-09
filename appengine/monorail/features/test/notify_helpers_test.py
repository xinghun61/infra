# -*- coding: utf8 -*-
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for notify_helpers.py."""

import unittest

from features import notify_helpers
from framework import emailfmt
from framework import framework_views
from services import service_manager
from testing import fake


REPLY_NOT_ALLOWED = notify_helpers.REPLY_NOT_ALLOWED
REPLY_MAY_COMMENT = notify_helpers.REPLY_MAY_COMMENT
REPLY_MAY_UPDATE = notify_helpers.REPLY_MAY_UPDATE


class ComputeIssueChangeAddressPermListTest(unittest.TestCase):

  def setUp(self):
    self.users_by_id = {
        111L: framework_views.UserView(111L, 'owner@example.com', True),
        222L: framework_views.UserView(222L, 'member@example.com', True),
        999L: framework_views.UserView(999L, 'visitor@example.com', True),
        }
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.owner = self.services.user.TestAddUser('owner@example.com', 111L)
    self.member = self.services.user.TestAddUser('member@example.com', 222L)
    self.visitor = self.services.user.TestAddUser('visitor@example.com', 999L)
    self.project = self.services.project.TestAddProject(
        'proj', owner_ids=[111L], committer_ids=[222L])
    self.project.process_inbound_email = True
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'summary', 'New', 111L)

  def testEmptyIDs(self):
    cnxn = 'fake cnxn'
    addr_perm_list = notify_helpers.ComputeIssueChangeAddressPermList(
        cnxn, [], self.project, self.issue, self.services, [], {},
        pref_check_function=lambda *args: True)
    self.assertEqual([], addr_perm_list)

  def testRecipientIsMember(self):
    cnxn = 'fake cnxn'
    ids_to_consider = [111L, 222L, 999L]
    addr_perm_list = notify_helpers.ComputeIssueChangeAddressPermList(
        cnxn, ids_to_consider, self.project, self.issue, self.services, set(),
        self.users_by_id, pref_check_function=lambda *args: True)
    self.assertEqual(
        [(True, 'owner@example.com', self.owner, REPLY_MAY_UPDATE),
         (True, 'member@example.com', self.member, REPLY_MAY_UPDATE),
         (False, 'visitor@example.com', self.visitor, REPLY_MAY_COMMENT)],
        addr_perm_list)


class ComputeProjectAndIssueNotificationAddrListTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService())
    self.project = self.services.project.TestAddProject('project')
    self.services.user.TestAddUser('alice@gmail.com', 111L)
    self.services.user.TestAddUser('bob@gmail.com', 222L)
    self.services.user.TestAddUser('fred@gmail.com', 555L)

  def testNotifyAddress(self):
    # No mailing list or filter rules are defined
    addr_perm_list = notify_helpers.ComputeProjectNotificationAddrList(
        self.project, True, set())
    self.assertListEqual([], addr_perm_list)

    # Only mailing list is notified.
    self.project.issue_notify_address = 'mailing-list@domain.com'
    addr_perm_list = notify_helpers.ComputeProjectNotificationAddrList(
        self.project, True, set())
    self.assertListEqual(
        [(False, 'mailing-list@domain.com', None, REPLY_NOT_ALLOWED)],
        addr_perm_list)

    # No one is notified because mailing list was already notified.
    omit_addrs = {'mailing-list@domain.com'}
    addr_perm_list = notify_helpers.ComputeProjectNotificationAddrList(
        self.project, False, omit_addrs)
    self.assertListEqual([], addr_perm_list)

    # No one is notified because anon users cannot view.
    addr_perm_list = notify_helpers.ComputeProjectNotificationAddrList(
        self.project, False, set())
    self.assertListEqual([], addr_perm_list)

  def testFilterRuleNotifyAddresses(self):
    issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'summary', 'New', 555L)
    issue.derived_notify_addrs.extend(['notify@domain.com'])

    addr_perm_list = notify_helpers.ComputeIssueNotificationAddrList(
        issue, set())
    self.assertListEqual(
        [(False, 'notify@domain.com', None, REPLY_NOT_ALLOWED)],
        addr_perm_list)

    # Also-notify addresses can be omitted (e.g., if it is the same as
    # the email address of the user who made the change).
    addr_perm_list = notify_helpers.ComputeIssueNotificationAddrList(
        issue, {'notify@domain.com'})
    self.assertListEqual([], addr_perm_list)


class MakeBulletedEmailWorkItemsTest(unittest.TestCase):

  def setUp(self):
    self.project = fake.Project(project_name='proj1')
    self.commenter_view = framework_views.UserView(
        111L, 'test@example.com', True)
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1234, 'summary', 'New', 111L)

  def testEmptyAddrs(self):
    """Test the case where we found zero users to notify."""
    email_tasks = notify_helpers.MakeBulletedEmailWorkItems(
        [], self.issue, 'body', 'body', self.project, 'example.com',
        self.commenter_view)
    self.assertEqual([], email_tasks)
    email_tasks = notify_helpers.MakeBulletedEmailWorkItems(
        [([], 'reason')], self.issue, 'body', 'body', self.project,
        'example.com', self.commenter_view)
    self.assertEqual([], email_tasks)


class MakeEmailWorkItemTest(unittest.TestCase):

  def setUp(self):
    self.project = fake.Project(project_name='proj1')
    self.project.process_inbound_email = True
    self.commenter_view = framework_views.UserView(
        111L, 'test@example.com', True)
    self.expected_html_footer = (
        'You received this message because:<br/>  1. reason<br/><br/>You may '
        'adjust your notification preferences at:<br/><a href="https://'
        'example.com/hosting/settings">https://example.com/hosting/settings'
        '</a>')
    self.services = service_manager.Services(
        user=fake.UserService())
    self.member = self.services.user.TestAddUser('member@example.com', 222L)
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1234, 'summary', 'New', 111L,
        project_name='proj1')

  def testBodySelection(self):
    """We send non-members the email body that is indented for non-members."""
    email_task = notify_helpers._MakeEmailWorkItem(
        (False, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, 'body non', 'body mem', self.project,
        'example.com', self.commenter_view)

    self.assertEqual('a@a.com', email_task['to'])
    self.assertEqual('Issue 1234 in proj1: summary', email_task['subject'])
    self.assertIn('body non', email_task['body'])
    self.assertEqual(
      emailfmt.FormatFromAddr(self.project, commenter_view=self.commenter_view,
                              can_reply_to=False),
      email_task['from_addr'])
    self.assertEqual(emailfmt.NoReplyAddress(), email_task['reply_to'])

    email_task = notify_helpers._MakeEmailWorkItem(
        (True, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, 'body mem', 'body mem', self.project,
        'example.com', self.commenter_view)
    self.assertIn('body mem', email_task['body'])

  def testHtmlBody_NoDetailUrl(self):
    """"An html body is not be sent if detail_url is not specified."""
    email_task = notify_helpers._MakeEmailWorkItem(
        (False, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, 'body non', 'body mem', self.project,
        'example.com', self.commenter_view, detail_url=None)

    self.assertIsNone(email_task['html_body'])

  def testHtmlBody_WithDetailUrl(self):
    """"An html body is sent if a detail_url is specified."""
    detail_url = 'http://test-detail-url.com/id=1234'
    email_task = notify_helpers._MakeEmailWorkItem(
        (False, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, 'body non', 'body mem', self.project,
        'example.com', self.commenter_view, detail_url=detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': detail_url,
            'body': 'body non-- <br/>%s' % self.expected_html_footer})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_WithUnicodeChars(self):
    """"An html body is sent if a detail_url is specified."""
    detail_url = 'http://test-detail-url.com/id=1234'
    unicode_content = '\xe2\x9d\xa4     â    â'
    email_task = notify_helpers._MakeEmailWorkItem(
        (False, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, unicode_content, 'unused body mem',
        self.project, 'example.com', self.commenter_view, detail_url=detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': detail_url,
            'body': '%s-- <br/>%s' % (unicode_content.decode('utf-8'),
                                      self.expected_html_footer)})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_WithLinks(self):
    """"An html body is sent if a detail_url is specified."""
    detail_url = 'http://test-detail-url.com/id=1234'
    email_task = notify_helpers._MakeEmailWorkItem(
        (False, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, 'test google.com test', 'unused body mem',
        self.project, 'example.com', self.commenter_view, detail_url=detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': detail_url,
            'body': (
            'test <a href="http://google.com">google.com</a> test-- <br/>%s' % (
                self.expected_html_footer))})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_LinkWithinTags(self):
    """"An html body is sent with correct <a href>s."""
    detail_url = 'http://test-detail-url.com/id=1234'
    email_task = notify_helpers._MakeEmailWorkItem(
        (False, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, 'test <http://google.com> test', 'unused body',
        self.project, 'example.com', self.commenter_view, detail_url=detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': detail_url,
            'body': (
                'test <a href="http://google.com"><http://google.com></a> '
                'test-- <br/>%s' % self.expected_html_footer)})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_EmailWithinTags(self):
    """"An html body is sent with correct <a href>s."""
    detail_url = 'http://test-detail-url.com/id=1234'
    email_task = notify_helpers._MakeEmailWorkItem(
        (False, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, 'test <t@chromium.org> <a@chromium.org> test',
        'unused body mem', self.project, 'example.com', self.commenter_view,
        detail_url=detail_url)

    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': detail_url,
            'body': (
                'test <a href="mailto:t@chromium.org"><t@chromium.org></a> '
                '<a href="mailto:a@chromium.org"><a@chromium.org></a> '
                'test-- <br/>%s' % self.expected_html_footer)})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testHtmlBody_WithEscapedHtml(self):
    """"An html body is sent with html content escaped."""
    detail_url = 'http://test-detail-url.com/id=1234'
    body_with_html_content = (
        '<a href="http://www.google.com">test</a> \'something\'')
    email_task = notify_helpers._MakeEmailWorkItem(
        (False, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, body_with_html_content, 'unused body mem',
        self.project, 'example.com', self.commenter_view, detail_url=detail_url)

    escaped_body_with_html_content = (
        '&lt;a href=&quot;http://www.google.com&quot;&gt;test&lt;/a&gt; '
        '&#39;something&#39;')
    notify_helpers._MakeNotificationFooter(
        ['reason'], REPLY_NOT_ALLOWED, 'example.com')
    expected_html_body = (
        notify_helpers.HTML_BODY_WITH_GMAIL_ACTION_TEMPLATE % {
            'url': detail_url,
            'body': '%s-- <br/>%s' % (escaped_body_with_html_content,
                                      self.expected_html_footer)})
    self.assertEquals(expected_html_body, email_task['html_body'])

  def testReplyInvitation(self):
    """We include a footer about replying that is appropriate for that user."""
    email_task = notify_helpers._MakeEmailWorkItem(
        (True, 'a@a.com', self.member, REPLY_NOT_ALLOWED),
        ['reason'], self.issue, 'body non', 'body mem', self.project,
        'example.com', self.commenter_view)
    self.assertEqual(emailfmt.NoReplyAddress(), email_task['reply_to'])
    self.assertNotIn('Reply to this email', email_task['body'])

    email_task = notify_helpers._MakeEmailWorkItem(
        (True, 'a@a.com', self.member, REPLY_MAY_COMMENT),
        ['reason'], self.issue, 'body non', 'body mem', self.project,
        'example.com', self.commenter_view)
    self.assertEqual(
      '%s@%s' % (self.project.project_name, emailfmt.MailDomain()),
      email_task['reply_to'])
    self.assertIn('Reply to this email to add a comment', email_task['body'])
    self.assertNotIn('make changes', email_task['body'])

    email_task = notify_helpers._MakeEmailWorkItem(
        (True, 'a@a.com', self.member, REPLY_MAY_UPDATE),
        ['reason'], self.issue, 'body non', 'body mem', self.project,
        'example.com', self.commenter_view)
    self.assertEqual(
      '%s@%s' % (self.project.project_name, emailfmt.MailDomain()),
      email_task['reply_to'])
    self.assertIn('Reply to this email to add a comment', email_task['body'])
    self.assertIn('make updates', email_task['body'])

  def testInboundEmailDisabled(self):
    """We don't invite replies if they are disabled for this project."""
    self.project.process_inbound_email = False
    email_task = notify_helpers._MakeEmailWorkItem(
        (True, 'a@a.com', self.member, REPLY_MAY_UPDATE),
        ['reason'], self.issue, 'body non', 'body mem', self.project,
        'example.com', self.commenter_view)
    self.assertEqual(emailfmt.NoReplyAddress(), email_task['reply_to'])

  def testReasons(self):
    """The footer lists reasons why that email was sent to that user."""
    email_task = notify_helpers._MakeEmailWorkItem(
        (True, 'a@a.com', self.member, REPLY_MAY_UPDATE),
        ['Funny', 'Caring', 'Near'], self.issue, 'body', 'body', self.project,
        'example.com', self.commenter_view)
    self.assertIn('because:', email_task['body'])
    self.assertIn('1. Funny', email_task['body'])
    self.assertIn('2. Caring', email_task['body'])
    self.assertIn('3. Near', email_task['body'])

    email_task = notify_helpers._MakeEmailWorkItem(
        (True, 'a@a.com', self.member, REPLY_MAY_UPDATE),
        [], self.issue, 'body', 'body', self.project,
        'example.com', self.commenter_view)
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
