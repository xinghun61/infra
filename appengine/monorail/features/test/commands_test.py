# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes and functions that implement command-line-like issue updates."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import unittest

from features import commands
from framework import framework_constants
from proto import tracker_pb2
from services import service_manager
from testing import fake
from tracker import tracker_bizobj
from tracker import tracker_constants


class CommandsTest(unittest.TestCase):

  def VerifyParseQuickEditCommmand(
      self, cmd, exp_summary='sum', exp_status='New', exp_owner_id=111,
      exp_cc_ids=None, exp_labels=None):

    issue = tracker_pb2.Issue()
    issue.project_name = 'proj'
    issue.local_id = 1
    issue.summary = 'sum'
    issue.status = 'New'
    issue.owner_id = 111
    issue.cc_ids.extend([222, 333])
    issue.labels.extend(['Type-Defect', 'Priority-Medium', 'Hot'])

    if exp_cc_ids is None:
      exp_cc_ids = [222, 333]
    if exp_labels is None:
      exp_labels = ['Type-Defect', 'Priority-Medium', 'Hot']

    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    logged_in_user_id = 999
    services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService())
    services.user.TestAddUser('jrobbins', 333)
    services.user.TestAddUser('jrobbins@jrobbins.org', 888)

    cnxn = 'fake cnxn'
    (summary, status, owner_id, cc_ids,
     labels) = commands.ParseQuickEditCommand(
         cnxn, cmd, issue, config, logged_in_user_id, services)
    self.assertEqual(exp_summary, summary)
    self.assertEqual(exp_status, status)
    self.assertEqual(exp_owner_id, owner_id)
    self.assertListEqual(exp_cc_ids, cc_ids)
    self.assertListEqual(exp_labels, labels)

  def testParseQuickEditCommmand_Empty(self):
    self.VerifyParseQuickEditCommmand('')  # Nothing should change.

  def testParseQuickEditCommmand_BuiltInFields(self):
    self.VerifyParseQuickEditCommmand(
        'status=Fixed', exp_status='Fixed')
    self.VerifyParseQuickEditCommmand(  # Normalized capitalization.
        'status=fixed', exp_status='Fixed')
    self.VerifyParseQuickEditCommmand(
        'status=limbo', exp_status='limbo')

    self.VerifyParseQuickEditCommmand(
        'owner=me', exp_owner_id=999)
    self.VerifyParseQuickEditCommmand(
        'owner=jrobbins@jrobbins.org', exp_owner_id=888)
    self.VerifyParseQuickEditCommmand(
        'owner=----', exp_owner_id=framework_constants.NO_USER_SPECIFIED)

    self.VerifyParseQuickEditCommmand(
        'summary=JustOneWord', exp_summary='JustOneWord')
    self.VerifyParseQuickEditCommmand(
        'summary="quoted sentence"', exp_summary='quoted sentence')
    self.VerifyParseQuickEditCommmand(
        "summary='quoted sentence'", exp_summary='quoted sentence')

    self.VerifyParseQuickEditCommmand(
        'cc=me', exp_cc_ids=[222, 333, 999])
    self.VerifyParseQuickEditCommmand(
        'cc=jrobbins@jrobbins.org', exp_cc_ids=[222, 333, 888])
    self.VerifyParseQuickEditCommmand(
        'cc=me,jrobbins@jrobbins.org',
        exp_cc_ids=[222, 333, 999, 888])
    self.VerifyParseQuickEditCommmand(
        'cc=-jrobbins,jrobbins@jrobbins.org',
        exp_cc_ids=[222, 888])

  def testParseQuickEditCommmand_Labels(self):
    self.VerifyParseQuickEditCommmand(
        'Priority=Low', exp_labels=['Type-Defect', 'Hot', 'Priority-Low'])
    self.VerifyParseQuickEditCommmand(
        'priority=low', exp_labels=['Type-Defect', 'Hot', 'Priority-Low'])
    self.VerifyParseQuickEditCommmand(
        'priority-low', exp_labels=['Type-Defect', 'Hot', 'Priority-Low'])
    self.VerifyParseQuickEditCommmand(
        '-priority-low', exp_labels=['Type-Defect', 'Priority-Medium', 'Hot'])
    self.VerifyParseQuickEditCommmand(
        '-priority-medium', exp_labels=['Type-Defect', 'Hot'])

    self.VerifyParseQuickEditCommmand(
        'Cold', exp_labels=['Type-Defect', 'Priority-Medium', 'Hot', 'Cold'])
    self.VerifyParseQuickEditCommmand(
        '+Cold', exp_labels=['Type-Defect', 'Priority-Medium', 'Hot', 'Cold'])
    self.VerifyParseQuickEditCommmand(
        '-Hot Cold', exp_labels=['Type-Defect', 'Priority-Medium', 'Cold'])
    self.VerifyParseQuickEditCommmand(
        '-Hot', exp_labels=['Type-Defect', 'Priority-Medium'])

  def testParseQuickEditCommmand_Multiple(self):
    self.VerifyParseQuickEditCommmand(
        'Priority=Low -hot owner:me cc:-jrobbins summary="other summary"',
        exp_summary='other summary', exp_owner_id=999,
        exp_cc_ids=[222], exp_labels=['Type-Defect', 'Priority-Low'])

  def testBreakCommandIntoParts_Empty(self):
    self.assertListEqual(
        [],
        commands._BreakCommandIntoParts(''))

  def testBreakCommandIntoParts_Single(self):
    self.assertListEqual(
        [('summary', 'new summary')],
        commands._BreakCommandIntoParts('summary="new summary"'))
    self.assertListEqual(
        [('summary', 'OneWordSummary')],
        commands._BreakCommandIntoParts('summary=OneWordSummary'))
    self.assertListEqual(
        [('key', 'value')],
        commands._BreakCommandIntoParts('key=value'))
    self.assertListEqual(
        [('key', 'value-with-dashes')],
        commands._BreakCommandIntoParts('key=value-with-dashes'))
    self.assertListEqual(
        [('key', 'value')],
        commands._BreakCommandIntoParts('key:value'))
    self.assertListEqual(
        [('key', 'value')],
        commands._BreakCommandIntoParts(' key:value '))
    self.assertListEqual(
        [('key', 'value')],
        commands._BreakCommandIntoParts('key:"value"'))
    self.assertListEqual(
        [('key', 'user@dom.com')],
        commands._BreakCommandIntoParts('key:user@dom.com'))
    self.assertListEqual(
        [('key', 'a@dom.com,-b@dom.com')],
        commands._BreakCommandIntoParts('key:a@dom.com,-b@dom.com'))
    self.assertListEqual(
        [(None, 'label')],
        commands._BreakCommandIntoParts('label'))
    self.assertListEqual(
        [(None, '-label')],
        commands._BreakCommandIntoParts('-label'))
    self.assertListEqual(
        [(None, '+label')],
        commands._BreakCommandIntoParts('+label'))

  def testBreakCommandIntoParts_Multiple(self):
    self.assertListEqual(
        [('summary', 'new summary'), (None, 'Hot'), (None, '-Cold'),
         ('owner', 'me'), ('cc', '+a,-b')],
        commands._BreakCommandIntoParts(
            'summary="new summary" Hot -Cold owner:me cc:+a,-b'))


class CommandSyntaxParsingTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        user=fake.UserService())

    self.services.project.TestAddProject('proj', owner_ids=[111])
    self.services.user.TestAddUser('a@example.com', 222)

    cnxn = 'fake connection'
    config = self.services.config.GetProjectConfig(cnxn, 789)

    for status in ['New', 'ReadyForReview']:
      config.well_known_statuses.append(tracker_pb2.StatusDef(
          status=status))

    for label in ['Prioity-Low', 'Priority-High']:
      config.well_known_labels.append(tracker_pb2.LabelDef(
          label=label))

    config.exclusive_label_prefixes.extend(
        tracker_constants.DEFAULT_EXCL_LABEL_PREFIXES)

    self.services.config.StoreConfig(cnxn, config)

  def testStandardizeStatus(self):
    config = self.services.config.GetProjectConfig('fake cnxn', 789)
    self.assertEqual('New',
                     commands._StandardizeStatus('NEW', config))
    self.assertEqual('New',
                     commands._StandardizeStatus('n$Ew ', config))
    self.assertEqual(
        'custom-label',
        commands._StandardizeLabel('custom=label ', config))

  def testStandardizeLabel(self):
    config = self.services.config.GetProjectConfig('fake cnxn', 789)
    self.assertEqual(
        'Priority-High',
        commands._StandardizeLabel('priority-high', config))
    self.assertEqual(
        'Priority-High',
        commands._StandardizeLabel('PRIORITY=HIGH', config))

  def testLookupMeOrUsername(self):
    self.assertEqual(
        123,
        commands._LookupMeOrUsername('fake cnxn', 'me', self.services, 123))

    self.assertEqual(
        222,
        commands._LookupMeOrUsername(
            'fake cnxn', 'a@example.com', self.services, 0))
