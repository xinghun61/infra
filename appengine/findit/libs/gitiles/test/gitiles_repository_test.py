# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from datetime import datetime
import json
import re

from testing_utils import testing

from gae_libs.testcase import TestCase
from libs.gitiles import gitiles_repository
from libs.gitiles.change_log import ChangeLog
from libs.http import retry_http_client


COMMIT_MESSAGE = ('Add popover for snapshot canvas log.\n'
                  'Review URL: https://codereview.chromium.org/320423004\n'
                  'Review URL: https://codereview.chromium.org/328113005\n'
                  'Cr-Commit-Position: refs/heads/master@{#175976}')

COMMIT_LOG = """)]}'
{
  "commit": "bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb",
  "tree": "481fd0f3bdf6eda5ca29ec6cbc6aa476b3684143",
  "parents": [
    "42a94bb5e2ef8525d7dadbd8eae37fe7cb8d77d0"
  ],
  "author": {
    "name": "test1@chromium.org",
    "email": "test1@chromium.org@bbb929c8-8fbe-4397-9dbb-9b2b20218538",
    "time": "Wed Jun 11 19:35:32 2014 -0400"
  },
  "committer": {
    "name": "test1@chromium.org",
    "email": "test1@chromium.org",
    "time": "Wed Jun 11 19:35:32 2014"
  },
  "message": %s,
  "tree_diff": [
    {
      "type": "add",
      "old_id": "f71f1167c2204626057d26912b8a2ff096fe4bd2",
      "old_mode": 33188,
      "old_path": "/dev/null",
      "new_id": "165fb11e0658f41d66038199056a53bcfab5dda0",
      "new_mode": 33188,
      "new_path": "Source/devtools/front_end/layers/added_file.js"
    },
    {
      "type": "delete",
      "old_id": "f71f1167c2204626057d26912b8a2ff096fe4bd3",
      "old_mode": 33188,
      "old_path": "Source/devtools/front_end/layers/deleted_file.js",
      "new_id": "165fb11e0658f41d66038199056a53bcfab5dda1",
      "new_mode": 33188,
      "new_path": "/dev/null"
    },
    {
      "type": "modify",
      "old_id": "f71f1167c2204626057d26912b8a2ff096fe4bd1",
      "old_mode": 33188,
      "old_path": "Source/devtools/front_end/layers/modified_file.js",
      "new_id": "165fb11e0658f41d66038199056a53bcfab5dda9",
      "new_mode": 33188,
      "new_path": "Source/devtools/front_end/layers/modified_file.js"
    },
    {
      "type": "copy",
      "old_id": "f71f1167c2204626057d26912b8a2ff096fe4bd4",
      "old_mode": 33188,
      "old_path": "Source/devtools/front_end/layers/file.js",
      "new_id": "165fb11e0658f41d66038199056a53bcfab5dda2",
      "new_mode": 33188,
      "new_path": "Source/devtools/front_end/layers/copied_file.js"
    },
    {
      "type": "rename",
      "old_id": "f71f1167c2204626057d26912b8a2ff096fe4bd5",
      "old_mode": 33188,
      "old_path": "Source/devtools/front_end/layers/file.js",
      "new_id": "165fb11e0658f41d66038199056a53bcfab5dda3",
      "new_mode": 33188,
      "new_path": "Source/devtools/front_end/layers/renamed_file.js"
    }
  ]
}""" % json.JSONEncoder().encode(COMMIT_MESSAGE)

EXPECTED_CHANGE_LOG_JSON = {
    'author': {
        'name': 'test1@chromium.org',
        'email': 'test1@chromium.org',
        'time': datetime(2014, 06, 11, 23, 35, 32),
    },
    'committer': {
        'name': 'test1@chromium.org',
        'email': 'test1@chromium.org',
        'time': datetime(2014, 06, 11, 19, 35, 32),
    },
    'message': COMMIT_MESSAGE,
    'commit_position': 175976,
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'Source/devtools/front_end/layers/added_file.js',
            'old_path': '/dev/null'
        },
        {
            'change_type': 'delete',
            'new_path': '/dev/null',
            'old_path': 'Source/devtools/front_end/layers/deleted_file.js'
        },
        {
            'change_type': 'modify',
            'new_path': 'Source/devtools/front_end/layers/modified_file.js',
            'old_path': 'Source/devtools/front_end/layers/modified_file.js'
        },
        {
            'change_type': 'copy',
            'new_path': 'Source/devtools/front_end/layers/copied_file.js',
            'old_path': 'Source/devtools/front_end/layers/file.js'
        },
        {
            'change_type': 'rename',
            'new_path': 'Source/devtools/front_end/layers/renamed_file.js',
            'old_path': 'Source/devtools/front_end/layers/file.js'
        }
    ],
    'commit_url':
        'https://repo.test/+/bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb',
    'code_review_url': 'https://codereview.chromium.org/328113005',
    'revision': 'bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb',
    'reverted_revision': None,
    'review_server_host': 'codereview.chromium.org',
    'review_change_id': '328113005',
}

COMMIT_LOG_WITH_UNKNOWN_FILE_CHANGE_TYPE = """)]}'
{
  "commit": "bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb",
  "tree": "481fd0f3bdf6eda5ca29ec6cbc6aa476b3684143",
  "parents": [
    "42a94bb5e2ef8525d7dadbd8eae37fe7cb8d77d0"
  ],
  "author": {
    "name": "test1@chromium.org",
    "email": "test1@chromium.org@bbb929c8-8fbe-4397-9dbb-9b2b20218538",
    "time": "Wed Jun 11 19:35:32 2014"
  },
  "committer": {
    "name": "test1@chromium.org",
    "email": "test1@chromium.org@bbb929c8-8fbe-4397-9dbb-9b2b20218538",
    "time": "Wed Jun 11 19:35:32 2014"
  },
  "message": "message",
  "tree_diff": [
    {
      "type": "unknown_change_type",
      "old_id": "f71f1167c2204626057d26912b8a2ff096fe4bd2",
      "old_mode": 33188,
      "old_path": "/dev/null",
      "new_id": "165fb11e0658f41d66038199056a53bcfab5dda0",
      "new_mode": 33188,
      "new_path": "Source/devtools/front_end/layers/added_file.js"
    }
  ]
}"""

GITILES_FILE_BLAME_RESULT = """)]}'
{
  "regions": [
    {
      "start": 1,
      "count": 6,
      "path": "chrome/test/chromedriver/element_commands.cc",
      "commit": "584ae1f26b070150f65a03dba75fc8af6b6f6ece",
      "author": {
        "name": "test2@chromium.org",
        "email": "test2@chromium.org@0039d316-1c4b-4281-b951-d872f2087c98",
        "time": "2013-02-11 20:18:51"
      }
    },
    {
      "start": 7,
      "count": 1,
      "path": "chrome/test/chromedriver/element_commands.cc",
      "commit": "030b5d9bb7d6c9f673cd8f0c86d8f1e921de7076",
      "author": {
        "name": "test3@chromium.org",
        "email": "test3@chromium.org@0039d316-1c4b-4281-b951-d872f2087c98",
        "time": "2014-02-06 10:02:10 +0400"
      }
    },
    {
      "start": 8,
      "count": 1,
      "path": "chrome/test/chromedriver/element_commands.cc",
      "commit": "584ae1f26b070150f65a03dba75fc8af6b6f6ece",
      "author": {
        "name": "test2@chromium.org",
        "email": "test2@chromium.org@0039d316-1c4b-4281-b951-d872f2087c98",
        "time": "2013-02-11 20:18:51"
      }
    }
  ]
}"""

EXPECTED_FILE_BLAME_JSON = {
    'regions': [
        {
            'count': 6,
            'author_email': u'test2@chromium.org',
            'author_time': datetime(2013, 02, 11, 20, 18, 51),
            'author_name': u'test2@chromium.org',
            'start': 1,
            'revision': u'584ae1f26b070150f65a03dba75fc8af6b6f6ece'
        },
        {
            'count': 1,
            'author_email': u'test3@chromium.org',
            'author_time': datetime(2014, 02, 06, 06, 02, 10),
            'author_name': u'test3@chromium.org',
            'start': 7,
            'revision': u'030b5d9bb7d6c9f673cd8f0c86d8f1e921de7076'
        },
        {
            'count': 1,
            'author_email': u'test2@chromium.org',
            'author_time': datetime(2013, 02, 11, 20, 18, 51),
            'author_name': u'test2@chromium.org',
            'start': 8,
            'revision': u'584ae1f26b070150f65a03dba75fc8af6b6f6ece'
        }
    ],
    'path': 'a/b/c.cc',
    'revision': 'dummy_abcd1234'
}

DUMMY_CHANGELOG_JSON = {
    'author': {
        'name': 'test@chromium.org',
        'email': 'test1@chromium.org',
        'time': datetime(2016, 01, 11, 23, 35, 32),
    },
    'committer': {
        'name': 'test1@chromium.org',
        'email': 'test@chromium.org',
        'time': datetime(2016, 01, 11, 19, 35, 32),
    },
    'message': 'dummy',
    'commit_position': 175976,
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'Source/devtools/added_file.js',
            'old_path': '/dev/null'
        }
    ],
    'commit_url':
        'https://repo.test/+/bcfd',
    'code_review_url': 'https://codereview.chromium.org/328113005',
    'revision': 'bcfd',
    'reverted_revision': None
}


class GitRepositoryTest(TestCase):

  def setUp(self):
    super(GitRepositoryTest, self).setUp()
    self.http_client_for_git = self.GetMockHttpClient()
    self.repo_url = 'https://repo.test'
    self.git_repo = gitiles_repository.GitilesRepository(
        self.http_client_for_git, self.repo_url)

  def testEndingSlashInRepoUrl(self):
    git_repo1 = gitiles_repository.GitilesRepository(
        self.http_client_for_git, self.repo_url)
    self.assertEqual(self.repo_url, git_repo1.repo_url)

    git_repo2 = gitiles_repository.GitilesRepository(
        self.http_client_for_git, '%s/' % self.repo_url)
    self.assertEqual(self.repo_url, git_repo2.repo_url)

  def testMalformattedJsonReponse(self):
    self.http_client_for_git.SetResponseForUrl(
        '%s/+/%s?format=json' % (self.repo_url, 'aaa'), 'abcde{"a": 1}')
    self.assertRaisesRegexp(
        Exception, re.escape('Response does not begin with )]}\'\n'),
        self.git_repo.GetChangeLog, 'aaa')

  def testGetChangeLog(self):
    self.http_client_for_git.SetResponseForUrl(
        '%s/+/%s?format=json' % (
            self.repo_url, 'bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb'),
        COMMIT_LOG)

    self.assertIsNone(self.git_repo.GetChangeLog('not_existing_revision'))

    change_log = self.git_repo.GetChangeLog(
        'bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb')
    self.assertEqual(EXPECTED_CHANGE_LOG_JSON, change_log.ToDict())

  def testUnknownChangeType(self):
    self.http_client_for_git.SetResponseForUrl(
        '%s/+/%s?format=json' % (
            self.repo_url, 'bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb'),
        COMMIT_LOG_WITH_UNKNOWN_FILE_CHANGE_TYPE)
    self.assertRaisesRegexp(
        Exception, 'Unknown change type "unknown_change_type"',
        self.git_repo.GetChangeLog, 'bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb')

  def testGetChangeDiff(self):
    self.assertIsNone(self.git_repo.GetChangeDiff('not_existing_revision'))

    git_revision = 'dummy_abcd1234'
    original_diff = 'dummy diff'
    self.http_client_for_git.SetResponseForUrl(
        '%s/+/%s%%5E%%21/?format=text' % (self.repo_url, git_revision),
        base64.b64encode(original_diff))
    diff = self.git_repo.GetChangeDiff(git_revision)
    self.assertEqual(original_diff, diff)

  def testGetBlame(self):
    self.assertIsNone(self.git_repo.GetBlame('path', 'not_existing_revision'))

    path = 'a/b/c.cc'
    git_revision = 'dummy_abcd1234'
    self.http_client_for_git.SetResponseForUrl(
        '%s/+blame/%s/%s?format=json' % (self.repo_url, git_revision, path),
        GITILES_FILE_BLAME_RESULT)

    blame = self.git_repo.GetBlame(path, git_revision)
    self.assertEqual(EXPECTED_FILE_BLAME_JSON, blame.ToDict())

  def testGetSource(self):
    self.assertIsNone(self.git_repo.GetSource('path', 'not_existing_revision'))

    path = 'a/b/c.cc'
    git_revision = 'dummy_abcd1234'
    original_source = 'dummy source'
    self.http_client_for_git.SetResponseForUrl(
        '%s/+/%s/%s?format=text' % (self.repo_url, git_revision, path),
        base64.b64encode(original_source))
    source = self.git_repo.GetSource(path, git_revision)
    self.assertEqual(original_source, source)

  def testTimeConversion(self):
    datetime_with_timezone = 'Wed Jul 22 19:35:32 2014 +0400'
    expected_datetime = datetime(2014, 7, 22, 15, 35, 32)
    utc_datetime = self.git_repo._GetDateTimeFromString(datetime_with_timezone)

    self.assertEqual(expected_datetime, utc_datetime)

  def testGetCommitsBetweenRevisions(self):
    def _MockSendRequestForJsonResponse(*_):
      return {
          'log': [
              {'commit': '3'},
              {'commit': '2'},
              {'commit': '1'}]
      }
    self.mock(gitiles_repository.GitilesRepository,
        '_SendRequestForJsonResponse', _MockSendRequestForJsonResponse)
    expected_commits = ['3', '2', '1']
    actual_commits = self.git_repo.GetCommitsBetweenRevisions('0', '3')
    self.assertEqual(expected_commits, actual_commits)

  def testGetCommitsBetweenRevisionsWithEmptyData(self):
    def _MockSendRequestForJsonResponse(*_):
      return None
    self.mock(gitiles_repository.GitilesRepository,
        '_SendRequestForJsonResponse', _MockSendRequestForJsonResponse)
    expected_commits = []
    actual_commits = self.git_repo.GetCommitsBetweenRevisions('0', '3')
    self.assertEqual(expected_commits, actual_commits)

  def testGetCommitsBetweenRevisionsWithIncompleteData(self):
    def _MockSendRequestForJsonResponse(*_):
      return {
          'log': [
              {'commit': '1'},
              {'something_else': '2'}
          ]
      }
    self.mock(gitiles_repository.GitilesRepository,
        '_SendRequestForJsonResponse', _MockSendRequestForJsonResponse)
    expected_commits = ['1']
    actual_commits = self.git_repo.GetCommitsBetweenRevisions('0', '3')
    self.assertEqual(expected_commits, actual_commits)

  def testGetCommitsBetweenRevisionsWithPaging(self):
    def _MockSendRequestForJsonResponse(*args, **_):
      url = args[1]
      if '0..3' in url:
        return {
            'log': [
                {'commit': '3'},
                {'commit': '2'}
            ],
            'next': '1'
        }
      else:
        return {
            'log': [
                {'commit': '1'}
            ]
        }

    self.mock(gitiles_repository.GitilesRepository,
        '_SendRequestForJsonResponse', _MockSendRequestForJsonResponse)
    expected_commits = ['3', '2', '1']
    actual_commits = self.git_repo.GetCommitsBetweenRevisions('0', '3', n=2)
    self.assertEqual(expected_commits, actual_commits)

  def testGetChangeLogs(self):
    def _MockSendRequestForJsonResponse(*_, **kargs):
      self.assertTrue(bool(kargs))
      return {'log': [json.loads(COMMIT_LOG[5:])]}

    self.mock(gitiles_repository.GitilesRepository,
        '_SendRequestForJsonResponse', _MockSendRequestForJsonResponse)

    changelogs = self.git_repo.GetChangeLogs('0', '2')
    self.assertEqual(len(changelogs), 1)
    self.assertEqual(changelogs[0].ToDict(), EXPECTED_CHANGE_LOG_JSON)

  def testGetChangeLogsNextPage(self):
    log1 = json.loads(COMMIT_LOG[5:])
    log1['commit'] = 'first_commit'
    log2 = log1.copy()
    log2['commit'] = 'next_page_commit'

    def _MockSendRequestForJsonResponse(_, url, **kargs):
      self.assertTrue(bool(kargs))
      if 'next' in url:
        return {'log': [log2]}

      return {'log': [log1], 'next': 'next_page_commit'}

    self.mock(gitiles_repository.GitilesRepository,
        '_SendRequestForJsonResponse', _MockSendRequestForJsonResponse)

    changelogs = self.git_repo.GetChangeLogs('0', '2')

    self.assertEqual(len(changelogs), 2)

  def testGetWrappedGitRepositoryClass(self):
    repo = gitiles_repository.GitilesRepository(
        self.http_client_for_git, 'http://repo_url')
    self.assertEqual(repo.repo_url, 'http://repo_url')
