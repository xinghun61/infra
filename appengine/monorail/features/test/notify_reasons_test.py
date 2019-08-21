# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for notify_reasons.py."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
import os

from google.appengine.api import taskqueue
from google.appengine.ext import testbed

from features import notify_reasons
from framework import emailfmt
from framework import framework_views
from framework import urls
from proto import user_pb2
from services import service_manager
from testing import fake
from tracker import tracker_bizobj


REPLY_NOT_ALLOWED = notify_reasons.REPLY_NOT_ALLOWED
REPLY_MAY_COMMENT = notify_reasons.REPLY_MAY_COMMENT
REPLY_MAY_UPDATE = notify_reasons.REPLY_MAY_UPDATE


class ComputeIssueChangeAddressPermListTest(unittest.TestCase):

  def setUp(self):
    self.users_by_id = {
        111: framework_views.StuffUserView(111, 'owner@example.com', True),
        222: framework_views.StuffUserView(222, 'member@example.com', True),
        999: framework_views.StuffUserView(999, 'visitor@example.com', True),
        }
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.owner = self.services.user.TestAddUser('owner@example.com', 111)
    self.member = self.services.user.TestAddUser('member@example.com', 222)
    self.visitor = self.services.user.TestAddUser('visitor@example.com', 999)
    self.project = self.services.project.TestAddProject(
        'proj', owner_ids=[111], committer_ids=[222])
    self.project.process_inbound_email = True
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'summary', 'New', 111)

  def testEmptyIDs(self):
    cnxn = 'fake cnxn'
    addr_perm_list = notify_reasons.ComputeIssueChangeAddressPermList(
        cnxn, [], self.project, self.issue, self.services, [], {})
    self.assertEqual([], addr_perm_list)

  def testRecipientIsMember(self):
    cnxn = 'fake cnxn'
    ids_to_consider = [111, 222, 999]
    addr_perm_list = notify_reasons.ComputeIssueChangeAddressPermList(
        cnxn, ids_to_consider, self.project, self.issue, self.services, set(),
        self.users_by_id, pref_check_function=lambda *args: True)
    self.assertEqual(
        [notify_reasons.AddrPerm(
            True, 'owner@example.com', self.owner, REPLY_MAY_UPDATE,
            user_pb2.UserPrefs(user_id=111)),
         notify_reasons.AddrPerm(
            True, 'member@example.com', self.member, REPLY_MAY_UPDATE,
            user_pb2.UserPrefs(user_id=222)),
         notify_reasons.AddrPerm(
            False, 'visitor@example.com', self.visitor, REPLY_MAY_COMMENT,
            user_pb2.UserPrefs(user_id=999))],
        addr_perm_list)


class ComputeProjectAndIssueNotificationAddrListTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService())
    self.project = self.services.project.TestAddProject('project')
    self.services.user.TestAddUser('alice@gmail.com', 111)
    self.services.user.TestAddUser('bob@gmail.com', 222)
    self.services.user.TestAddUser('fred@gmail.com', 555)

  def testNotifyAddress(self):
    # No mailing list or filter rules are defined
    addr_perm_list = notify_reasons.ComputeProjectNotificationAddrList(
        self.cnxn, self.services, self.project, True, set())
    self.assertListEqual([], addr_perm_list)

    # Only mailing list is notified.
    self.project.issue_notify_address = 'mailing-list@domain.com'
    addr_perm_list = notify_reasons.ComputeProjectNotificationAddrList(
        self.cnxn, self.services, self.project, True, set())
    self.assertListEqual(
        [notify_reasons.AddrPerm(
            False, 'mailing-list@domain.com', None, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs())],
        addr_perm_list)

    # No one is notified because mailing list was already notified.
    omit_addrs = {'mailing-list@domain.com'}
    addr_perm_list = notify_reasons.ComputeProjectNotificationAddrList(
        self.cnxn, self.services, self.project, False, omit_addrs)
    self.assertListEqual([], addr_perm_list)

    # No one is notified because anon users cannot view.
    addr_perm_list = notify_reasons.ComputeProjectNotificationAddrList(
        self.cnxn, self.services, self.project, False, set())
    self.assertListEqual([], addr_perm_list)

  def testFilterRuleNotifyAddresses(self):
    issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'summary', 'New', 555)
    issue.derived_notify_addrs.extend(['notify@domain.com'])

    addr_perm_list = notify_reasons.ComputeIssueNotificationAddrList(
        self.cnxn, self.services, issue, set())
    self.assertListEqual(
        [notify_reasons.AddrPerm(
            False, 'notify@domain.com', None, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs())],
        addr_perm_list)

    # Also-notify addresses can be omitted (e.g., if it is the same as
    # the email address of the user who made the change).
    addr_perm_list = notify_reasons.ComputeIssueNotificationAddrList(
        self.cnxn, self.services, issue, {'notify@domain.com'})
    self.assertListEqual([], addr_perm_list)


class ComputeGroupReasonListTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        features=fake.FeaturesService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.project = self.services.project.TestAddProject(
      'project', project_id=789)
    self.config = self.services.config.GetProjectConfig('cnxn', 789)
    self.alice = self.services.user.TestAddUser('alice@example.com', 111)
    self.bob = self.services.user.TestAddUser('bob@example.com', 222)
    self.fred = self.services.user.TestAddUser('fred@example.com', 555)
    self.users_by_id = framework_views.MakeAllUserViews(
        'cnxn', self.services.user, [111, 222, 555])
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'summary', 'New', 555)

  def CheckGroupReasonList(
      self, actual, reporter_apl=None, owner_apl=None, old_owner_apl=None,
      default_owner_apl=None, ccd_apl=None, default_ccd_apl=None,
      starrer_apl=None, subscriber_apl=None, also_notified_apl=None,
      all_notifications_apl=None):
    (you_report, you_own, you_old_owner, you_default_owner,
     you_ccd, you_default_ccd, you_star, you_subscribe, you_also_notify,
     all_notifications) = actual
    self.assertEqual(
        (reporter_apl or [], notify_reasons.REASON_REPORTER),
        you_report)
    self.assertEqual(
        (owner_apl or [], notify_reasons.REASON_OWNER),
        you_own)
    self.assertEqual(
        (old_owner_apl or [], notify_reasons.REASON_OLD_OWNER),
        you_old_owner)
    self.assertEqual(
        (default_owner_apl or [], notify_reasons.REASON_DEFAULT_OWNER),
        you_default_owner)
    self.assertEqual(
        (ccd_apl or [], notify_reasons.REASON_CCD),
        you_ccd)
    self.assertEqual(
        (default_ccd_apl or [], notify_reasons.REASON_DEFAULT_CCD),
        you_default_ccd)
    self.assertEqual(
        (starrer_apl or [], notify_reasons.REASON_STARRER),
        you_star)
    self.assertEqual(
        (subscriber_apl or [], notify_reasons.REASON_SUBSCRIBER),
        you_subscribe)
    self.assertEqual(
        (also_notified_apl or [], notify_reasons.REASON_ALSO_NOTIFY),
        you_also_notify)
    self.assertEqual(
        (all_notifications_apl or [], notify_reasons.REASON_ALL_NOTIFICATIONS),
        all_notifications)

  def testComputeGroupReasonList_OwnerAndCC(self):
    """Fred owns the issue, Alice is CC'd."""
    self.issue.cc_ids = [self.alice.user_id]
    actual = notify_reasons.ComputeGroupReasonList(
        'cnxn', self.services, self.project, self.issue, self.config,
        self.users_by_id, [], True)
    self.CheckGroupReasonList(
        actual,
        owner_apl=[notify_reasons.AddrPerm(
            False, self.fred.email, self.fred, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.fred.user_id))],
        ccd_apl=[notify_reasons.AddrPerm(
            False, self.alice.email, self.alice, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.alice.user_id))])

  def testComputeGroupReasonList_Starrers(self):
    """Bob and Alice starred it, but Alice opts out of notifications."""
    self.alice.notify_starred_issue_change = False
    actual = notify_reasons.ComputeGroupReasonList(
        'cnxn', self.services, self.project, self.issue, self.config,
        self.users_by_id, [], True,
        starrer_ids=[self.alice.user_id, self.bob.user_id])
    self.CheckGroupReasonList(
        actual,
        owner_apl=[notify_reasons.AddrPerm(
            False, self.fred.email, self.fred, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.fred.user_id))],
        starrer_apl=[notify_reasons.AddrPerm(
            False, self.bob.email, self.bob, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.bob.user_id))])

  def testComputeGroupReasonList_Subscribers(self):
    """Bob subscribed."""
    sq = tracker_bizobj.MakeSavedQuery(
          1, 'freds issues', 1, 'owner:fred@example.com',
          subscription_mode='immediate', executes_in_project_ids=[789])
    self.services.features.UpdateUserSavedQueries(
        'cnxn', self.bob.user_id, [sq])
    actual = notify_reasons.ComputeGroupReasonList(
        'cnxn', self.services, self.project, self.issue, self.config,
        self.users_by_id, [], True)
    self.CheckGroupReasonList(
        actual,
        owner_apl=[notify_reasons.AddrPerm(
            False, self.fred.email, self.fred, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.fred.user_id))],
        subscriber_apl=[notify_reasons.AddrPerm(
            False, self.bob.email, self.bob, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.bob.user_id))])

    # Now with subscriber notifications disabled.
    actual = notify_reasons.ComputeGroupReasonList(
        'cnxn', self.services, self.project, self.issue, self.config,
        self.users_by_id, [], True, include_subscribers=False)
    self.CheckGroupReasonList(
        actual,
        owner_apl=[notify_reasons.AddrPerm(
            False, self.fred.email, self.fred, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.fred.user_id))])

  def testComputeGroupReasonList_NotifyAll(self):
    """Project is configured to always notify issues@example.com."""
    self.project.issue_notify_address = 'issues@example.com'
    actual = notify_reasons.ComputeGroupReasonList(
        'cnxn', self.services, self.project, self.issue, self.config,
        self.users_by_id, [], True)
    self.CheckGroupReasonList(
        actual,
        owner_apl=[notify_reasons.AddrPerm(
            False, self.fred.email, self.fred, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.fred.user_id))],
        all_notifications_apl=[notify_reasons.AddrPerm(
            False, 'issues@example.com', None, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs())])

    # We don't use the notify-all address when the issue is not public.
    actual = notify_reasons.ComputeGroupReasonList(
        'cnxn', self.services, self.project, self.issue, self.config,
        self.users_by_id, [], False)
    self.CheckGroupReasonList(
        actual,
        owner_apl=[notify_reasons.AddrPerm(
            False, self.fred.email, self.fred, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.fred.user_id))])

    # Now with the notify-all address disabled.
    actual = notify_reasons.ComputeGroupReasonList(
        'cnxn', self.services, self.project, self.issue, self.config,
        self.users_by_id, [], True, include_notify_all=False)
    self.CheckGroupReasonList(
        actual,
        owner_apl=[notify_reasons.AddrPerm(
            False, self.fred.email, self.fred, REPLY_NOT_ALLOWED,
            user_pb2.UserPrefs(user_id=self.fred.user_id))])
