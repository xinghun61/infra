# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import os
import sys
import textwrap
import unittest

_ROOT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
sys.path.insert(1, _ROOT_DIR)
from local_libs import script_util
script_util.SetUpSystemPaths()

from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles import change_log
from local_libs.git_checkout import local_git_parsers


class LocalGitParsersTest(unittest.TestCase):

  def setUp(self):
    super(LocalGitParsersTest, self).setUp()
    self.blame_parser = local_git_parsers.GitBlameParser()

  def testGitBlameParser(self):
    output = textwrap.dedent("""
        revision_hash 18 18 3
        author test@google.com
        author-mail <test@google.com@2bbb7eff-a529-9590-31e7-b0007b416f81>
        author-time 1363032816
        author-tz +0000
        committer test@google.com
        committer-mail <test@google.com@2bbb7eff-a529-9590-31e7-b0007b416f81>
        committer-time 1363032816
        committer-tz +0000
        summary add (mac) test for ttcindex in SkFontStream
        previous fe7533eebe777cc66c7f8fa7a03f00572755c5b4 src/core/SkFont.h
        filename src/core/SkFont.h
                     *  blabla line 1
        revision_hash 19 19
                     *  blabla line 2
        revision_hash 20 20
                     *  blabla line 3

        revision_hash 29 29 2
                     *  blabla line 4
        """)

    expected_blame = Blame('src/core/SkFont.h', 'rev')
    mock_email = 'test@google.com'
    author_time = datetime(2013, 03, 11, 17, 13, 36)
    expected_blame.AddRegions([
        Region(18, 3, 'revision_hash', mock_email, mock_email, author_time),
        Region(29, 2, 'revision_hash', mock_email, mock_email, author_time)
    ])

    blame_result = self.blame_parser(output, 'src/core/SkFont.h', 'rev')
    self.assertTrue(blame_result.revision, expected_blame.revision)
    self.assertTrue(blame_result.path, expected_blame.path)
    for region, expected_region in zip(blame_result, expected_blame):
      self.assertTrue(region.ToDict(), expected_region.ToDict())

  def testGitBlameParserEmptyOutput(self):
    blame_result = self.blame_parser('', 'src/core/SkFont.h', 'rev')
    self.assertIsNone(blame_result)

  def testGitBlameParserDummyOutput(self):
    blame_result = self.blame_parser('Dummy', 'src/core/SkFont.h', 'rev')
    self.assertIsNone(blame_result)

  def testGetFileChangeInfo(self):
    self.assertIsNone(
        local_git_parsers.GetFileChangeInfo('unknown change type', None, None))

  def testGitChangeLogParser(self):
    output = textwrap.dedent("""
        commit revision
        tree tree_revision
        parents parent_revision

        author Test
        author-mail test@google.com
        author-time 2016-07-13 20:37:06

        committer Test
        committer-mail test@google.com
        committer-time 2016-07-13 20:37:06

        --Message start--
        Revert commit messages...
        > Committed: https://c.com/+/c9cc182781484f9010f062859cda048afefefefe
        Review-Url: https://codereview.chromium.org/2391763002
        Cr-Commit-Position: refs/heads/master@{#425880}
        --Message end--

        :100644 100644 25f95f c766f1 M      src/a/b.py
        :100644 100644 25aa5f c777f1 X      src/a/c.py
        """)

    message = ('Revert commit messages...\n'
               '> Committed: https://c.com/+/'
               'c9cc182781484f9010f062859cda048afefefefe\n'
               'Review-Url: https://codereview.chromium.org/2391763002\n'
               'Cr-Commit-Position: refs/heads/master@{#425880}')

    expected_changelog = change_log.ChangeLog(
        change_log.Contributor('Test', 'test@google.com',
                               datetime(2016, 7, 13, 20, 37, 6)),
        change_log.Contributor('Test', 'test@google.com',
                               datetime(2016, 7, 13, 20, 37,
                                        6)), 'revision', 425880, message,
        [change_log.FileChangeInfo('modify', 'src/a/b.py', 'src/a/b.py')],
        'https://repo/+/revision', 'https://codereview.chromium.org/2391763002',
        'c9cc182781484f9010f062859cda048afefefefe')

    changelog = local_git_parsers.GitChangeLogParser()(output, 'https://repo')
    self.assertDictEqual(expected_changelog.ToDict(), changelog.ToDict())

  def testGitChangeLogParserParseEmptyOutput(self):
    self.assertIsNone(local_git_parsers.GitChangeLogParser()(None, 'repo'))

  def testGitChangeLogsParser(self):
    output = textwrap.dedent("""
        **Changelog start**
        commit rev1
        tree 27b0421273ed4aea25e497c6d26d9c7db6481852
        parents rev22c9e

        author author1
        author-mail author1@chromium.org
        author-time 2016-06-02 10:55:38

        committer Commit bot
        committer-mail commit-bot@chromium.org
        committer-time 2016-06-02 10:57:13

        --Message start--
        Message 1
        --Message end--

        :100644 100644 28e117 f12d3 D      a/b.py


        **Changelog start**
        commit rev2
        tree d22d3786e135b83183cfeba5f3d8913959f56299
        parents ac7ee4ce7b8d39b22a710c58d110e0039c11cf9a

        author author2
        author-mail author2@chromium.org
        author-time 2016-06-02 10:53:03

        committer Commit bot
        committer-mail commit-bot@chromium.org
        committer-time 2016-06-02 10:54:14

        --Message start--
        Message 2
        --Message end--

        :100644 100644 7280f df186 A      b/c.py

        **Changelog start**
        commit rev3
        tree d22d3786e135b83183cfeba5f3d8913959f56299
        parents ac7ee4ce7b8d39b22a710c58d110e0039c11cf9a

        author author3
        author-mail author3@chromium.org
        author-time 2016-06-02 10:53:03

        committer Commit bot
        committer-mail commit-bot@chromium.org
        committer-time 2016-06-02 10:54:14

        --Message start--
        Message 3
        --Message end--

        :100644 100644 3f2e 20a5 R078 b/c.py b/cc.py
        """)

    expected_changelogs = [
        change_log.ChangeLog(
            change_log.Contributor('author1', 'author1@chromium.org',
                                   datetime(2016, 6, 2, 10, 55, 38)),
            change_log.Contributor('Commit bot', 'commit-bot@chromium.org',
                                   datetime(2016, 6, 2, 10, 57,
                                            13)), 'rev1', None, 'Message 1',
            [change_log.FileChangeInfo('delete', 'a/b.py', None)],
            'http://repo/+/rev1', None, None),
        change_log.ChangeLog(
            change_log.Contributor('author2', 'author2@chromium.org',
                                   datetime(2016, 6, 2, 10, 53, 3)),
            change_log.Contributor('Commit bot', 'commit-bot@chromium.org',
                                   datetime(2016, 6, 2, 10, 54,
                                            14)), 'rev2', None, 'Message 2',
            [change_log.FileChangeInfo('add', None, 'b/c.py')],
            'http://repo/+/rev2', None, None),
        change_log.ChangeLog(
            change_log.Contributor('author3', 'author3@chromium.org',
                                   datetime(2016, 6, 2, 10, 53, 3)),
            change_log.Contributor('Commit bot', 'commit-bot@chromium.org',
                                   datetime(2016, 6, 2, 10, 54,
                                            14)), 'rev3', None, 'Message 3',
            [change_log.FileChangeInfo('rename', 'b/c.py', 'b/cc.py')],
            'http://repo/+/rev3', None, None),
    ]

    changelogs = local_git_parsers.GitChangeLogsParser()(output, 'http://repo')
    for changelog, expected_changelog in zip(changelogs, expected_changelogs):
      self.assertEqual(changelog.ToDict(), expected_changelog.ToDict())

  def testGitChangeLogsParserParseEmptyOutput(self):
    self.assertIsNone(local_git_parsers.GitChangeLogsParser()(None, 'repo'))

  def testGitChangeLogsParserWithEmptyChangelog(self):
    output = '**Changelog start**\nblablabla'
    self.assertEqual(local_git_parsers.GitChangeLogsParser()(output,
                                                             'http://repo'), [])

  def testGitDiffParser(self):
    self.assertEqual('output', local_git_parsers.GitDiffParser()('output'))

  def testGitCommitsParser(self):
    output = textwrap.dedent("""
        5789567 (HEAD -> master) Move some Document timers to frame-specific...
        95bbc94 Add a feature flag for the security verbose
        463b55a Disable system health smoke tests on Nexus5.
        3e84f37 Fix use-after-free introduced by ...
        """)
    self.assertListEqual(local_git_parsers.GitCommitsParser()(output),
                         ['5789567', '95bbc94', '463b55a', '3e84f37'])

if __name__ == '__main__':
  unittest.main()
