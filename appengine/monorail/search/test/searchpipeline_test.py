# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the searchpipeline module."""

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
    self.services.user.TestAddUser('a@example.com', 111L)

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

  def testReplaceKeywordsWithUserID(self):
    pass  # TODO(jrobbins): write tests


if __name__ == '__main__':
  unittest.main()
