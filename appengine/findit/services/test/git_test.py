# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
from datetime import datetime
from datetime import timedelta
import mock

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.gitiles.change_log import ChangeLog
from libs import time_util
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from services import git
from waterfall.test import wf_testcase

SOME_TIME = datetime(2018, 1, 1, 1)


class GitTest(wf_testcase.WaterfallTestCase):

  def _MockGetBlame(self, path, revision):
    blame = Blame(revision, path)

    blame.AddRegions([
        Region(1, 2, '7', u'test3@chromium.org', u'test3@chromium.org',
               datetime(2015, 06, 07, 04, 35, 32)),
        Region(3, 3, '5', u'test3@chromium.org', u'test3@chromium.org',
               datetime(2015, 06, 05, 04, 35, 32)),
        Region(7, 1, '8', u'test2@chromium.org', u'test2@chromium.org',
               datetime(2015, 06, 8, 04, 35, 32)),
        Region(8, 1, '7', u'test3@chromium.org', u'test3@chromium.org',
               datetime(2015, 06, 07, 21, 35, 32)),
        Region(9, 10, '12', u'test3@chromium.org', u'test3@chromium.org',
               datetime(2015, 06, 12, 04, 35, 32))
    ])
    return blame

  def testGetGitBlame(self):
    repo_url = 'https://chromium.googlesource.com/chromium/src.git'
    revision = '8'
    file_path = 'a/b/c.cc'
    self.mock(CachedGitilesRepository, 'GetBlame', self._MockGetBlame)
    blame = git.GetGitBlame(repo_url, revision, file_path)
    self.assertIsNotNone(blame)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLogs')
  def testPullChangelogs(self, mock_fn):
    change_log_rev1_dict = {
        'author': {
            'name':
                'someone@chromium.org',
            'email':
                'someone@chromium.org',
            'time':
                datetime.strptime('Wed Jun 11 19:35:32 2014',
                                  '%a %b %d %H:%M:%S %Y'),
        },
        'committer': {
            'name':
                'someone@chromium.org',
            'email':
                'someone@chromium.org',
            'time':
                datetime.strptime('Wed Jun 11 19:35:32 2014',
                                  '%a %b %d %H:%M:%S %Y'),
        },
        'message':
            'Cr-Commit-Position: refs/heads/master@{#175976}',
        'commit_position':
            175976,
        'touched_files': [{
            'new_path': 'added_file.js',
            'change_type': 'add',
            'old_path': '/dev/null'
        }],
        'commit_url':
            'https://chromium.googlesource.com/chromium/src.git/+log/rev0',
        'code_review_url':
            None,
        'revision':
            'rev1',
        'reverted_revision':
            None,
        'review_server_host':
            None,
        'review_change_id':
            None,
    }
    change_log_rev1 = ChangeLog.FromDict(change_log_rev1_dict)
    mock_fn.return_value = [change_log_rev1]

    expected_change_logs = {'rev1': change_log_rev1}

    change_logs = git.PullChangeLogs('rev0', 'rev1')
    self.assertEqual(expected_change_logs, change_logs)

  def testPullChangelogsNoStartRevision(self):
    self.assertEqual({}, git.PullChangeLogs(None, 'rev1'))

  def _MockGetChangeLog(self, revision):

    class Author(namedtuple('Author', ['name', 'email'])):
      pass

    class MockedChangeLog(object):

      def __init__(self, commit_position, code_review_url):
        self.commit_position = commit_position
        self.code_review_url = code_review_url
        self.change_id = str(commit_position)
        self.author = Author('author', 'author@abc.com')

    mock_change_logs = {}
    mock_change_logs['rev1'] = None
    mock_change_logs['rev2'] = MockedChangeLog(123, 'url')
    return mock_change_logs.get(revision)

  def _GenerateGetNChangeLogsMock(self, delta, next_rev='next_rev'):
    """Makes a mock that returns n changelogs `delta` time apart."""

    def _inner(_self, _revision, n):

      class Committer(namedtuple('Author', ['name', 'email', 'time'])):
        pass

      class MockedChangeLog(object):

        def __init__(self, commit_position, t):
          self.commit_position = commit_position
          self.change_id = str(commit_position)
          self.committer = Committer('committer', 'committer@abc.com', t)

      result = []

      end_commit_position = 100
      end_datetime = SOME_TIME
      for i in range(n):
        result.append(
            MockedChangeLog(end_commit_position - i,
                            end_datetime - (i * delta)))
      return result, next_rev

    return _inner

  def testGetCulpritInfo(self):
    failed_revisions = ['rev1', 'rev2']

    self.mock(CachedGitilesRepository, 'GetChangeLog', self._MockGetChangeLog)

    expected_culprits = {
        'rev1': {
            'revision': 'rev1',
            'repo_name': 'chromium'
        },
        'rev2': {
            'revision': 'rev2',
            'repo_name': 'chromium',
            'commit_position': 123,
            'url': 'url',
            'author': 'author@abc.com'
        }
    }
    self.assertEqual(expected_culprits, git.GetCLInfo(failed_revisions))

  @mock.patch.object(git, 'GetCLInfo')
  def testGetCommitPositionFromRevision(self, mocked_cl_info):
    requested_revision = 'r1'
    expected_commit_position = 1000
    mocked_cl_info.return_value = {
        requested_revision: {
            'revision': requested_revision,
            'repo_name': 'chromium',
            'commit_position': expected_commit_position,
            'url': 'url',
            'author': 'author@abc.com'
        }
    }
    self.assertEqual(expected_commit_position,
                     git.GetCommitPositionFromRevision(requested_revision))

  @mock.patch.object(
      CachedGitilesRepository,
      'GetCommitsBetweenRevisions',
      return_value=['r4', 'r3', 'r2', 'r1'])
  def testGetCommitsBetweenRevisionsInOrderAscending(self, _):
    self.assertEqual(['r1', 'r2', 'r3', 'r4'],
                     git.GetCommitsBetweenRevisionsInOrder('r0', 'r4', True))

  @mock.patch.object(
      CachedGitilesRepository,
      'GetCommitsBetweenRevisions',
      return_value=['r4', 'r3', 'r2', 'r1'])
  def testGetCommitsBetweenRevisionsInOrderDescending(self, _):
    self.assertEqual(['r4', 'r3', 'r2', 'r1'],
                     git.GetCommitsBetweenRevisionsInOrder('r0', 'r4', False))

  def testCountRecentCommitsFew(self):
    self.mock(
        CachedGitilesRepository,
        'GetNChangeLogs',
        self._GenerateGetNChangeLogsMock(timedelta(minutes=25)))
    self.mock(time_util, 'GetUTCNow', lambda: SOME_TIME)
    self.assertEqual(3, git.CountRecentCommits('url'))

  def testCountRecentCommitsMany(self):
    self.mock(
        CachedGitilesRepository,
        'GetNChangeLogs',
        self._GenerateGetNChangeLogsMock(timedelta(minutes=1)))
    self.mock(time_util, 'GetUTCNow', lambda: SOME_TIME)
    self.assertTrue(10 <= git.CountRecentCommits('url'))

  def testCountRecentCommitsNormal(self):
    self.mock(
        CachedGitilesRepository,
        'GetNChangeLogs',
        self._GenerateGetNChangeLogsMock(timedelta(minutes=10)))
    self.mock(time_util, 'GetUTCNow', lambda: SOME_TIME)
    self.assertEqual(7, git.CountRecentCommits('url'))

  def testCountRecentCommitsNoNext(self):
    self.mock(CachedGitilesRepository, 'GetNChangeLogs',
              self._GenerateGetNChangeLogsMock(
                  timedelta(minutes=1), next_rev=None))
    self.mock(time_util, 'GetUTCNow', lambda: SOME_TIME)
    self.assertTrue(10 <= git.CountRecentCommits('url'))

  def testCountRecentCommitsNoLogs(self):
    self.mock(CachedGitilesRepository, 'GetNChangeLogs',
              lambda self, r, n: ([], None))
    self.mock(time_util, 'GetUTCNow', lambda: SOME_TIME)
    self.assertEqual(0, git.CountRecentCommits('url'))
