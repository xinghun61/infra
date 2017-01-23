# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import os
import shutil
import subprocess
import tempfile
import textwrap

from testing_utils import testing

from git_checkout import local_git_repository
from libs.gitiles import blame
from libs.gitiles import change_log
import local_cache
import script_util


class LocalGitRepositoryTest(testing.AppengineTestCase):

  def setUp(self):
    super(LocalGitRepositoryTest, self).setUp()
    self.temp_dir = tempfile.mkdtemp(prefix='local_git_repository_test')
    self.mock(subprocess, 'check_call', lambda *args, **kwargs: None)
    self.mock(local_cache, 'CACHE_DIR', self.temp_dir)
    self.local_repo = local_git_repository.LocalGitRepository(
        'https://repo/path')

  def tearDown(self):
    shutil.rmtree(self.temp_dir, ignore_errors=True)
    super(LocalGitRepositoryTest, self).tearDown()

  def testCloneOrUpdateRepoIfRepoNotExists(self):
    self.mock(os.path, 'exists', lambda path: False)
    repo = local_git_repository.LocalGitRepository('http://repo1')
    repo._CloneOrUpdateRepoIfNeeded()
    self.assertTrue(self.local_repo.repo_url in
                    local_git_repository.LocalGitRepository._updated_repos)

  def testCloneOrUpdateRepoIfRepoExistsButNotUpdated(self):
    self.mock(os.path, 'exists', lambda path: True)
    repo = local_git_repository.LocalGitRepository('http://repo2')
    repo._CloneOrUpdateRepoIfNeeded()
    self.assertTrue(self.local_repo.repo_url in
                    local_git_repository.LocalGitRepository._updated_repos)

  def testInit(self):
    repo = local_git_repository.LocalGitRepository(None)
    self.assertIsNone(repo.repo_url)

    repo_url = 'https://repo/path'
    self.mock(local_git_repository.LocalGitRepository,
        '_CloneOrUpdateRepoIfNeeded', lambda *_: None)
    repo = local_git_repository.LocalGitRepository(repo_url)
    self.assertEqual(repo.repo_url, repo_url)

  def testGetChangeLog(self):
    output = textwrap.dedent(
        """
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
        blabla
        --Message end--

        :100644 100644 25f95f c766f1 M      src/a/b.py
        """
    )

    expected_changelog = change_log.ChangeLog(
        change_log.Contributor('Test', 'test@google.com',
                               datetime(2016, 7, 13, 20, 37, 6)),
        change_log.Contributor('Test', 'test@google.com',
                               datetime(2016, 7, 13, 20, 37, 6)),
        'revision', None, 'blabla',
        [change_log.FileChangeInfo('modify', 'src/a/b.py', 'src/a/b.py')],
        'https://repo/path/+/revision', None, None)
    self.mock(script_util, 'GetCommandOutput', lambda *_: output)
    # TODO: compare the objects directly, rather than via ToDict
    self.assertDictEqual(self.local_repo.GetChangeLog('revision').ToDict(),
                         expected_changelog.ToDict())

  def testGetChangeLogNoneCommandOutput(self):
    self.mock(script_util, 'GetCommandOutput', lambda *_: None)
    self.assertIsNone(self.local_repo.GetChangeLog('revision'))

  def testGetChangeLogs(self):
    output = textwrap.dedent(
        """
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
        """
    )

    expected_changelogs = [
        change_log.ChangeLog(
            change_log.Contributor('author1', 'author1@chromium.org',
                                   datetime(2016, 6, 2, 10, 55, 38)),
            change_log.Contributor('Commit bot', 'commit-bot@chromium.org',
                                   datetime(2016, 6, 2, 10, 57, 13)),
            'rev1', None, 'Message 1',
            [change_log.FileChangeInfo('delete', 'a/b.py', None)],
            'https://repo/path/+/rev1', None, None),
        change_log.ChangeLog(
            change_log.Contributor('author2', 'author2@chromium.org',
                                   datetime(2016, 6, 2, 10, 53, 3)),
            change_log.Contributor('Commit bot', 'commit-bot@chromium.org',
                                   datetime(2016, 6, 2, 10, 54, 14)),
            'rev2', None, 'Message 2',
            [change_log.FileChangeInfo('add', None, 'b/c.py')],
            'https://repo/path/+/rev2', None, None),
    ]

    self.mock(script_util, 'GetCommandOutput', lambda *_: output)
    changelogs = self.local_repo.GetChangeLogs('rev0', 'rev2')
    for changelog, expected_changelog in zip(changelogs, expected_changelogs):
      # TODO(katesonia): Add __eq__ in changelog to compare.
      self.assertEqual(changelog.ToDict(), expected_changelog.ToDict())

  def testGetChangeLogsNoneCommandOutput(self):
    self.mock(script_util, 'GetCommandOutput', lambda *_: None)
    self.assertIsNone(self.local_repo.GetChangeLogs('rev0', 'rev2'))

  def testGetChangeDiff(self):
    self.mock(script_util, 'GetCommandOutput', lambda *_: 'diff')
    self.assertEqual(self.local_repo.GetChangeDiff('rev'), 'diff')
    self.assertEqual(self.local_repo.GetChangeDiff('rev', 'file_path'), 'diff')

  def testGetChangeDiffNoneCommandOutput(self):
    self.mock(script_util, 'GetCommandOutput', lambda *_: None)
    self.assertIsNone(self.local_repo.GetChangeDiff('rev'))

  def testGetBlame(self):
    output = textwrap.dedent(
        """
        revision_hash 18 18 3
        author test@google.com
        author-mail <test@google.com@2bbb7eff-a529-9590-31e7-b0007b416f81>
        author-time 2013-03-11 17:13:36
        committer test@google.com
        committer-mail <test@google.com@2bbb7eff-a529-9590-31e7-b0007b416f81>
        committer-time 2013-03-11 17:13:36
        summary add (mac) test for ttcindex in SkFontStream
        previous fe7533eebe777cc66c7f8fa7a03f00572755c5b4 src/core/SkFont.h
        filename src/core/SkFont.h
                     *  blabla line 1
        revision_hash 19 19
                     *  blabla line 2
        revision_hash 20 20
                     *  blabla line 3
        """
    )
    self.mock(script_util, 'GetCommandOutput', lambda *_: output)
    expected_blame = blame.Blame('src/core/SkFont.h', 'rev')
    expected_blame.AddRegions([
      blame.Region(18, 3, 'revision_hash', 'test@google.com', 'test@google.com',
                   datetime(2013, 03, 11, 17, 13, 36))])

    blame_result = self.local_repo.GetBlame('src/core/SkFont.h', 'rev')
    self.assertTrue(blame_result.revision, expected_blame.revision)
    self.assertTrue(blame_result.path, expected_blame.path)
    # TODO(katesonia): Switch to use __eq__ in blame.
    for region, expected_region in zip(blame_result, expected_blame):
      self.assertTrue(region.ToDict(), expected_region.ToDict())

  def testGetBlameNoneCommandOutput(self):
    self.mock(script_util, 'GetCommandOutput', lambda *_: None)
    self.assertIsNone(self.local_repo.GetBlame('src/core/SkFont.h', 'rev'))

  def testGetSource(self):
    self.mock(script_util, 'GetCommandOutput', lambda *_: 'source')
    self.assertEqual(self.local_repo.GetSource('file_path', 'rev'), 'source')

  def testGetSourceNoneCommandOutput(self):
    self.mock(script_util, 'GetCommandOutput', lambda *_: None)
    self.assertIsNone(self.local_repo.GetSource('file_path', 'rev'))

  def testGetLocalGitCommandOutput(self):
    class _MockProcess(object):
      def __init__(self, command, *_):
        self.command = command

      def communicate(self, *_):
        return self.command, 'error'

      @property
      def returncode(self):
        return 1 if self.command == 'dummy' else 0

    self.mock(subprocess, 'Popen', lambda command, **_: _MockProcess(command))
    output = script_util.GetCommandOutput('command')
    self.assertEqual(output, 'command')

    self.assertRaisesRegexp(Exception, 'Error running command dummy: error',
                            script_util.GetCommandOutput, 'dummy')
