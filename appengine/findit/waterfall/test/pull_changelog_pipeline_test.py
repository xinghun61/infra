# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import handlers
from testing_utils import testing

from waterfall.pull_changelog_pipeline import PullChangelogPipeline


REV1_COMMIT_LOG = """)]}'
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
  "message": "git-svn-id: svn://svn.chromium.org/chromium/src@175976 blabla",
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

REV1_COMMIT_LOG_URL = ('https://chromium.googlesource.com/chromium/src.git'
                       '/+/rev1')
REV1_COMMIT_JSON_URL = '%s?format=json' % REV1_COMMIT_LOG_URL


class PullChangelogPipelineTest(testing.AppengineTestCase):
  app_module = handlers._APP

  def testPullChangelogs(self):
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(REV1_COMMIT_JSON_URL, REV1_COMMIT_LOG)

    failure_info = {
      'failed': True,
      'builds': {
        '999': {
          'blame_list': ['rev1']
        }
      }
    }

    expected_change_logs = {
      'rev1': {
        'author_name': 'someone@chromium.org',
        'message':
          'git-svn-id: svn://svn.chromium.org/chromium/src@175976 blabla',
        'committer_email': 'someone@chromium.org',
        'commit_position': 175976,
        'author_email': 'someone@chromium.org',
        'touched_files': [
          {
            'new_path': 'added_file.js',
            'change_type': 'add',
            'old_path': '/dev/null'
          }
        ],
        'author_time': datetime.strptime('Wed Jun 11 19:35:32 2014',
            '%a %b %d %H:%M:%S %Y'),
        'committer_time': datetime.strptime('Wed Jun 11 19:35:32 2014',
            '%a %b %d %H:%M:%S %Y'),
        'commit_url': REV1_COMMIT_LOG_URL,
        'code_review_url': None,
        'committer_name': 'someone@chromium.org',
        'revision': 'rev1'
      }
    }

    pipeline = PullChangelogPipeline()
    change_logs = pipeline.run(failure_info)
    self.assertEqual(expected_change_logs, change_logs)

  def testBailOutIfNotAFailedBuild(self):
    failure_info = {
        'failed': False,
    }
    expected_change_logs = {}

    pipeline = PullChangelogPipeline()
    change_logs = pipeline.run(failure_info)
    self.assertEqual(expected_change_logs, change_logs)
