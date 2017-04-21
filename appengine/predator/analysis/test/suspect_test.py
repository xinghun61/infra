# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from analysis.stacktrace import StackFrame
from analysis.suspect import Suspect
from libs.gitiles.change_log import ChangeLog

DUMMY_CHANGELOG1 = ChangeLog.FromDict({
    'author': {
        'name': 'r@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'email': 'r',
        'time': 'Thu Mar 31 21:28:39 2016',
        'name': 'example@chromium.org',
    },
    'message': 'dummy',
    'commit_position': 175900,
    'touched_files': [
        {
            'change_type': 'modify',
            'new_path': 'a.cc',
            'old_path': 'a.cc',
        },
        {
            'change_type': 'modify',
            'new_path': 'b.cc',
            'old_path': 'b.cc',
        },
    ],
    'commit_url':
        'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '1',
    'reverted_revision': None
})

DUMMY_CHANGELOG2 = ChangeLog.FromDict({
    'author': {
        'name': 'e@chromium.org',
        'email': 'e@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'name': 'e',
        'email': 'e@chromium.org',
        'time': 'Thu Mar 31 21:28:39 2016',
    },
    'message': 'dummy',
    'commit_position': 175911,
    'touched_files': [
        {
            'change_type': 'modify',
            'new_path': 'a.cc',
            'old_path': 'a.cc',
        },
    ],
    'commit_url':
        'https://repo.test/+/2',
    'code_review_url': 'https://codereview.chromium.org/3290',
    'revision': '2',
    'reverted_revision': None
})


class SuspectTest(unittest.TestCase):

  def testSuspectToDict(self):
    suspect = Suspect(DUMMY_CHANGELOG1, 'src/',
                      confidence=1, reasons=['MinDistance', 0.5, 'some reason'],
                      changed_files={'file': 'f', 'blame_url': 'http://b',
                                     'info': 'min distance (LOC) 5'})

    expected_suspect_json = {
        'url': DUMMY_CHANGELOG1.commit_url,
        'review_url': DUMMY_CHANGELOG1.code_review_url,
        'revision': DUMMY_CHANGELOG1.revision,
        'project_path': 'src/',
        'author': DUMMY_CHANGELOG1.author.email,
        'time': str(DUMMY_CHANGELOG1.author.time),
        'reasons': ['MinDistance', 0.5, 'some reason'],
        'changed_files': {'file': 'f', 'blame_url': 'http://b',
                          'info': 'min distance (LOC) 5'},
        'confidence': 1,
    }

    self.assertDictEqual(suspect.ToDict(), expected_suspect_json)

  def testSuspectToString(self):
    suspect = Suspect(DUMMY_CHANGELOG1, 'src/', confidence=1)
    self.assertEqual(suspect.ToString(), str(suspect.ToDict()))
    self.assertEqual(str(suspect), str(suspect.ToDict()))
