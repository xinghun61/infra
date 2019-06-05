# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the searchpipeline module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import ast_pb2
from proto import tracker_pb2
from search import searchpipeline
from services import service_manager
from testing import fake
from tracker import tracker_bizobj


class SearchPipelineTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.services = service_manager.Services(
        user=fake.UserService(),
        project=fake.ProjectService(),
        issue=fake.IssueService(),
        config=fake.ConfigService())
    self.services.user.TestAddUser('a@example.com', 111)

  def testIsStarredRE(self):
    """IS_STARRED_RE matches only the is:starred term."""
    input_output = {
      'something:else': 'something:else',
      'genesis:starred': 'genesis:starred',
      'is:starred-in-bookmarks': 'is:starred-in-bookmarks',
      'is:starred': 'foo',
      'Is:starred': 'foo',
      'is:STARRED': 'foo',
      'is:starred is:open': 'foo is:open',
      'is:open is:starred': 'is:open foo',
      }
    for i, o in input_output.items():
      self.assertEqual(o, searchpipeline.IS_STARRED_RE.sub('foo', i))

  def testMeRE(self):
    """ME_RE matches only the 'me' value keyword."""
    input_output = {
      'something:else': 'something:else',
      'else:some': 'else:some',
      'me': 'me',  # It needs to have a ":" in front.
      'cc:me-team': 'cc:me-team',
      'cc:me=domain@otherdomain': 'cc:me=domain@otherdomain',
      'cc:me@example.com': 'cc:me@example.com',
      'me:the-boss': 'me:the-boss',
      'cc:me': 'cc:foo',
      'cc=me': 'cc=foo',
      'owner:Me': 'owner:foo',
      'reporter:ME': 'reporter:foo',
      'cc:me is:open': 'cc:foo is:open',
      'is:open cc:me': 'is:open cc:foo',
      }
    for i, o in input_output.items():
      self.assertEqual(o, searchpipeline.ME_RE.sub('foo', i))

  def testAccumulateIssueProjectsAndConfigs(self):
    pass  # TODO(jrobbins): write tests

  def testReplaceKeywordsWithUserIDs_IsStarred(self):
    """The term is:starred is replaced with starredby:USERID."""
    actual, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
        [111], 'is:starred')
    self.assertEqual('starredby:111', actual)
    self.assertEqual([], warnings)

    actual, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
        [111], 'Pri=1 is:starred M=61')
    self.assertEqual('Pri=1 starredby:111 M=61', actual)
    self.assertEqual([], warnings)

    actual, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
        [], 'Pri=1 is:starred M=61')
    self.assertEqual('Pri=1  M=61', actual)
    self.assertEqual(
        ['"is:starred" ignored because you are not signed in.'],
        warnings)

  def testReplaceKeywordsWithUserIDs_IsStarred_linked(self):
    """is:starred is replaced by starredby:uid1,uid2 for linked accounts."""
    actual, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
        [111, 222], 'is:starred')
    self.assertEqual('starredby:111,222', actual)
    self.assertEqual([], warnings)

  def testReplaceKeywordsWithUserIDs_Me(self):
    """Terms like owner:me are replaced with owner:USERID."""
    actual, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
        [111], 'owner:me')
    self.assertEqual('owner:111', actual)
    self.assertEqual([], warnings)

    actual, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
        [111], 'Pri=1 cc:me M=61')
    self.assertEqual('Pri=1 cc:111 M=61', actual)
    self.assertEqual([], warnings)

    actual, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
        [], 'Pri=1 reporter:me M=61')
    self.assertEqual('Pri=1  M=61', actual)
    self.assertEqual(
        ['"me" keyword ignored because you are not signed in.'],
        warnings)

  def testReplaceKeywordsWithUserIDs_Me_LinkedAccounts(self):
    """owner:me is replaced with owner:uid,uid for each linked account."""
    actual, warnings = searchpipeline.ReplaceKeywordsWithUserIDs(
        [111, 222], 'owner:me')
    self.assertEqual('owner:111,222', actual)
    self.assertEqual([], warnings)

  def testParseQuery(self):
    pass  # TODO(jrobbins): write tests
