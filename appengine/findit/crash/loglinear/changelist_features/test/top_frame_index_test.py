# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from crash.loglinear.changelist_features import top_frame_index
from crash.suspect import Suspect
from crash.suspect import StackInfo
from crash.stacktrace import StackFrame
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType
import libs.math.logarithms as lmath


_MAXIMUM = 7

_DUMMY_CHANGELOG = ChangeLog.FromDict({
    'author': {
        'name': 'r@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'name': 'example@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:28:39 2016',
    },
    'message': 'dummy',
    'commit_position': 175900,
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'a.cc',
            'old_path': None,
        },
    ],
    'commit_url':
        'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '1',
    'reverted_revision': None
})


class TopFrameIndexFeatureTest(unittest.TestCase):
  """Tests ``TopFrameIndexFeature``."""

  def _GetDummyChangeLog(self):
    return _DUMMY_CHANGELOG

  def _GetDummyReport(self):
    return None

  def _GetMockSuspect(self):
    """Returns a ``Suspect`` with the desired top frame index."""
    dep_path = 'src/'
    return Suspect(self._GetDummyChangeLog(), dep_path)

  def testTopFrameIndexNone(self):
    """Test that the feature returns log(0) when there are no matched files."""
    report = self._GetDummyReport()
    suspect = Suspect(self._GetDummyChangeLog(), 'src/')
    self.assertEqual(
        lmath.LOG_ZERO,
        top_frame_index.TopFrameIndexFeature(3)(report)(
            suspect, {}).value)

  def testTopFrameIndexIsZero(self):
    """Test that the feature returns log(1) when the top frame index is 0."""
    report = self._GetDummyReport()
    suspect = self._GetMockSuspect()
    touched_file_to_stack_infos = {
        FileChangeInfo(ChangeType.MODIFY, 'a.cc', 'a.cc'):
        [StackInfo(frame=StackFrame(index=0,
                                    dep_path=suspect.dep_path,
                                    function='func',
                                    file_path='a.cc',
                                    raw_file_path='a.cc',
                                    crashed_line_numbers=[7]),
                   priority = 0)]
    }
    self.assertEqual(lmath.LOG_ONE,
                     top_frame_index.TopFrameIndexFeature(_MAXIMUM)(report)(
                         suspect, touched_file_to_stack_infos).value)
