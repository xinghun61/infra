# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
from datetime import datetime

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from services import git
from waterfall.test import wf_testcase


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

  def testPullChangelogs(self):

    rev1_commit_log = """)]}'
    {
      "commit": "rev1",
      "tree": "tree_rev",
      "parents": [
        "rev0"
      ],
      "author": {
        "name": "someone@chromium.org",
        "email": "someone@chromium.org",
        "time": "Wed Jun 11 19:35:32 2014"
      },
      "committer": {
        "name": "someone@chromium.org",
        "email": "someone@chromium.org",
        "time": "Wed Jun 11 19:35:32 2014"
      },
      "message": "Cr-Commit-Position: refs/heads/master@{#175976}",
      "tree_diff": [
        {
          "type": "add",
          "old_id": "id1",
          "old_mode": 33188,
          "old_path": "/dev/null",
          "new_id": "id2",
          "new_mode": 33188,
          "new_path": "added_file.js"
        }
      ]
    }
    """
    rev1_commit_log_url = ('https://chromium.googlesource.com/chromium/src.git'
                           '/+/rev1')
    rev1_commit_json_url = '%s?format=json' % rev1_commit_log_url

    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(rev1_commit_json_url, rev1_commit_log)

    failure_info = {
        'failed': True,
        'chromium_revision': 'rev1',
        'builds': {
            '999': {
                'blame_list': ['rev1']
            }
        }
    }

    expected_change_logs = {
        'rev1': {
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
                rev1_commit_log_url,
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
    }

    change_logs = git.PullChangeLogs(failure_info)
    self.assertEqual(expected_change_logs, change_logs)

  def testPullChangelogsFailed(self):

    rev1_commit_log = """)]}'\n{}"""
    rev1_commit_log_url = ('https://chromium.googlesource.com/chromium/src.git'
                           '/+/rev1')
    rev1_commit_json_url = '%s?format=json' % rev1_commit_log_url

    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(rev1_commit_json_url, rev1_commit_log)

    failure_info = {
        'failed': True,
        'chromium_revision': 'rev1',
        'builds': {
            '999': {
                'blame_list': ['rev1']
            }
        }
    }

    with self.assertRaises(Exception):
      git.PullChangeLogs(failure_info)

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

  def testGetCLKeysFromCLInfo(self):
    cl_info = {
        'rev1': {
            'revision': u'rev1',
            'repo_name': u'chromium'
        },
        'rev2': {
            'revision': u'rev2',
            'repo_name': u'chromium',
            'commit_position': 123,
            'url': 'url'
        }
    }

    expected_cl_keys = {
        'rev1': {
            'repo_name': u'chromium',
            'revision': u'rev1'
        },
        'rev2': {
            'repo_name': u'chromium',
            'revision': u'rev2'
        }
    }

    self.assertEqual(expected_cl_keys,
                     git.GetCLKeysFromCLInfo(cl_info).ToSerializable())
