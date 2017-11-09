# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from services import git
from waterfall.test import wf_testcase


class GitTest(wf_testcase.WaterfallTestCase):

  def _MockGetChangeLog(self, revision):

    class MockedChangeLog(object):

      def __init__(self, commit_position, code_review_url):
        self.commit_position = commit_position
        self.code_review_url = code_review_url
        self.change_id = str(commit_position)

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
            'url': 'url'
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
