# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from datetime import datetime
import json
import re

from testing_utils import testing

from common import git_repository
from common import retry_http_client


COMMIT_MESSAGE = ('Add popover for snapshot canvas log.\n\n'
                  'Review URL: https://codereview.chromium.org/320423004\n\n'
                  'Review URL: https://codereview.chromium.org/328113005\n\n'
                  'git-svn-id: svn://svn.chromium.org/blink/trunk@175976 '
                  'bbb929c8-8fbe-4397-9dbb-9b2b20218538\n')

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
    'author_name': 'test1@chromium.org',
    'message': COMMIT_MESSAGE,
    'committer_email': 'test1@chromium.org',
    'commit_position': 175976,
    'author_email': 'test1@chromium.org',
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
    'author_time': datetime(2014, 06, 11, 23, 35, 32),
    'committer_time': datetime(2014, 06, 11, 19, 35, 32),
    'commit_url':
        'https://repo.test/+/bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb',
    'code_review_url': 'https://codereview.chromium.org/328113005',
    'committer_name': 'test1@chromium.org',
    'revision': 'bcfd5a12eea05588aee98b7cf7e032d8cb5b58bb',
    'reverted_revision': None
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


class HttpClientForGit(retry_http_client.RetryHttpClient):

  def __init__(self):
    super(HttpClientForGit, self).__init__()
    self.response_for_url = {}

  def SetResponseForUrl(self, url, response):
    self.response_for_url[url] = response

  def GetBackoff(self, *_):  # pragma: no cover
    """Override to avoid sleep."""
    return 0

  def _Get(self, url, *_):
    response = self.response_for_url.get(url)
    if response is None:
      return 404, 'Not Found'
    else:
      return 200, response

  def _Post(self, *_):  # pragma: no cover
    pass


class GitRepositoryTest(testing.AppengineTestCase):

  def setUp(self):
    super(GitRepositoryTest, self).setUp()
    self.http_client_for_git = HttpClientForGit()
    self.repo_url = 'https://repo.test'
    self.git_repo = git_repository.GitRepository(self.repo_url,
                                                 self.http_client_for_git)

  def testExtractCommitPositionAndCodeReviewUrl(self):
    testcases = [
        {
            'message':
                'balabala...\n'
                '\n'
                'BUG=409934\n'
                '\n'
                'Review URL: https://codereview.chromium.org/547753003\n'
                '\n'
                'Cr-Commit-Position: refs/heads/master@{#293661}',
            'commit_position': 293661,
            'code_review_url': 'https://codereview.chromium.org/547753003',
        },
        {
            'message':
                'balabala...\n'
                '\n'
                'balabala...\n'
                '\n'
                'R=test4@chromium.org\n'
                '\n'
                'Review URL: https://codereview.chromium.org/469523002\n'
                '\n'
                'Cr-Commit-Position: refs/heads/master@{#289120}\n'
                'git-svn-id: svn://svn.chromium.org/chrome/trunk/src@289120 '
                '0039d316-1c4b-4281-b951-d872f2087c98',
            'commit_position': 289120,
            'code_review_url': 'https://codereview.chromium.org/469523002',
        },
        {
            'message':
                'balabala...\n'
                '\n'
                'BUG=none\n'
                'NOTRY=true\n'
                '\n'
                'Review URL: https://chromiumcodereview.appspot.com/18862002\n'
                '\n'
                'git-svn-id: svn://svn.chromium.org/chrome/trunk/src@210392 '
                '0039d316-1c4b-4281-b951-d872f2087c98',
            'commit_position': 210392,
            'code_review_url':
                'https://chromiumcodereview.appspot.com/18862002',
        },
        {
            'message':
                'balabala...\n'
                '\n'
                'BUG=none\n'
                'NOTRY=true\n'
                '\n'
                'Review URL: https://chromiumcodereview.appspot.com/1862002 .\n'
                '\n'
                'git-svn-id: svn://svn.chromium.org/chrome/trunk/src@12345 '
                '0039d316-1c4b-4281-b951-d872f2087c98',
            'commit_position': 12345,
            'code_review_url':
                'https://chromiumcodereview.appspot.com/1862002',
        },
        {
            'message': None,
            'commit_position': None,
            'code_review_url': None
        }
    ]

    for testcase in testcases:
      (commit_position,
       code_review_url) = self.git_repo.ExtractCommitPositionAndCodeReviewUrl(
           testcase['message'])
      self.assertEqual(commit_position, testcase['commit_position'])
      self.assertEqual(code_review_url, testcase['code_review_url'])

  def testEndingSlashInRepoUrl(self):
    git_repo1 = git_repository.GitRepository(self.repo_url,
                                             self.http_client_for_git)
    self.assertEqual(self.repo_url, git_repo1.repo_url)

    git_repo2 = git_repository.GitRepository('%s/' % self.repo_url,
                                             self.http_client_for_git)
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

  def testGetRevertedRevision(self):
    message = (
        'Revert of test1\n\nReason for revert:\nrevert test1\n\n'
        'Original issue\'s description:\n> test 1\n>\n'
        '> description of test 1.\n>\n> BUG=none\n> TEST=none\n'
        '> R=test@chromium.org\n> TBR=test@chromium.org\n>\n'
        '> Committed: https://chromium.googlesource.com/chromium/src/+/'
        'c9cc182781484f9010f062859cda048afefefefe\n'
        '> Cr-Commit-Position: refs/heads/master@{#341992}\n\n'
        'TBR=test@chromium.org\nNOPRESUBMIT=true\nNOTREECHECKS=true\n'
        'NOTRY=true\nBUG=none\n\n'
        'Review URL: https://codereview.chromium.org/1278653002\n\n'
        'Cr-Commit-Position: refs/heads/master@{#342013}\n')

    reverted_revision = self.git_repo.GetRevertedRevision(message)
    self.assertEqual('c9cc182781484f9010f062859cda048afefefefe',
                     reverted_revision)

  def testGetRevertedRevisionRevertOfRevert(self):
    message = (
        'Revert of Revert\n\nReason for revert:\nRevert of revert\n\n'
        'Original issue\'s description:\n> test case of revert of revert\n>\n'
        '> Reason for revert:\n> reason\n>\n> Original issue\'s description:\n'
        '> > base cl\n> >\n> > R=kalman\n> > BUG=424661\n> >\n'
        '> > Committed: https://crrev.com/34ea66b8ac1d56dadd670431063857ffdd\n'
        '> > Cr-Commit-Position: refs/heads/master@{#326953}\n>\n'
        '> TBR=test@chromium.org\n> NOPRESUBMIT=true\n'
        '> NOTREECHECKS=true\n> NOTRY=true\n> BUG=424661\n>\n'
        '> Committed: https://crrev.com/76a7e3446188256ca240dc31f78de29511a'
        '2c322\n'
        '> Cr-Commit-Position: refs/heads/master@{#327021}\n\n'
        'TBR=test@chromium.org\nNOPRESUBMIT=true\n'
        'NOTREECHECKS=true\nNOTRY=true\nBUG=424661\n\n'
        'Review URL: https://codereview.chromium.org/1161773008\n\n'
        'Cr-Commit-Position: refs/heads/master@{#332062}\n')

    reverted_revision = self.git_repo.GetRevertedRevision(message)
    self.assertEqual('76a7e3446188256ca240dc31f78de29511a2c322',
                     reverted_revision)

  def testGetRevertedRevisionNoRevertedCL(self):
    message = (
        'Test for not revert cl\n\n'
        'TBR=test@chromium.org\nNOPRESUBMIT=true\n'
        'NOTREECHECKS=true\nNOTRY=true\nBUG=424661\n\n'
        'Review URL: https://codereview.chromium.org/1161773008\n\n'
        'Cr-Commit-Position: refs/heads/master@{#332062}\n')

    reverted_revision = self.git_repo.GetRevertedRevision(message)
    self.assertIsNone(reverted_revision)

  def testGetCommitsBetweenRevisions(self):
    def _MockSendRequestForJsonResponse(*_):
      return {
          'log': [
              {'commit': '3'},
              {'commit': '2'},
              {'commit': '1'}]
      }
    self.mock(git_repository.GitRepository, '_SendRequestForJsonResponse',
              _MockSendRequestForJsonResponse)
    expected_commits = ['3', '2', '1']
    actual_commits = self.git_repo.GetCommitsBetweenRevisions('0', '3')
    self.assertEqual(expected_commits, actual_commits)

  def testGetCommitsBetweenRevisionsWithEmptyData(self):
    def _MockSendRequestForJsonResponse(*_):
      return None
    self.mock(git_repository.GitRepository, '_SendRequestForJsonResponse',
              _MockSendRequestForJsonResponse)
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
    self.mock(git_repository.GitRepository, '_SendRequestForJsonResponse',
              _MockSendRequestForJsonResponse)
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

    self.mock(git_repository.GitRepository, '_SendRequestForJsonResponse',
              _MockSendRequestForJsonResponse)
    expected_commits = ['3', '2', '1']
    actual_commits = self.git_repo.GetCommitsBetweenRevisions('0', '3', n=2)
    self.assertEqual(expected_commits, actual_commits)
