# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.change_log import ChangeLog
from testing_utils import testing

DUMMY_CHANGELOG = ChangeLog.FromDict({
    'author_name': 'r@chromium.org',
    'message': 'dummy',
    'committer_email': 'r@chromium.org',
    'commit_position': 175900,
    'author_email': 'r@chromium.org',
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'a.cc',
            'old_path': None,
        },
    ],
    'author_time': 'Thu Mar 31 21:24:43 2016',
    'committer_time': 'Thu Mar 31 21:28:39 2016',
    'commit_url':
        'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'committer_name': 'example@chromium.org',
    'revision': '1',
    'reverted_revision': None
})


class ScorerTestSuite(testing.AppengineTestCase):  # pragma: no cover.

  def _GetDummyChangeLog(self):
    return DUMMY_CHANGELOG
