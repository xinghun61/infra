# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from crash.loglinear.changelist_features import top_frame_index
from crash.suspect import Suspect
from crash.suspect import StackInfo
from crash.stacktrace import StackFrame
from libs.gitiles.change_log import ChangeLog
import libs.math.logarithms as lmath


_MAXIMUM = float(top_frame_index._MAX_FRAME_INDEX)

_DUMMY_CHANGELOG = ChangeLog.FromDict({
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


class TopFrameIndexTest(unittest.TestCase):

  def _GetDummyChangeLog(self):
    return _DUMMY_CHANGELOG

  def _GetDummyReport(self):
    return None

  def _GetMockSuspect(self, mock_top_frame_index):
    """Returns a ``Suspect`` with the desired top frame index."""
    dep_path = 'src/'
    suspect = Suspect(self._GetDummyChangeLog(), dep_path)
    suspect.file_to_stack_infos = {
        'a.cc': [StackInfo(
            frame = StackFrame(
                index = mock_top_frame_index,
                dep_path = dep_path,
                function = 'func',
                file_path = 'a.cc',
                raw_file_path = 'a.cc',
                crashed_line_numbers = [7]),
            priority = 0)]
    }
    return suspect

  def testTopFrameIndexNone(self):
    """Test that the feature returns log(0) when there are no frames."""
    report = self._GetDummyReport()
    suspect = Suspect(self._GetDummyChangeLog(), 'src/')
    self.assertEqual(lmath.LOG_ZERO,
        top_frame_index.TopFrameIndexFeature()(report)(suspect).value)

  def testTopFrameIndexIsZero(self):
    """Test that the feature returns log(1) when the top frame index is 0."""
    report = self._GetDummyReport()
    suspect = self._GetMockSuspect(0)
    self.assertEqual(lmath.LOG_ONE,
        top_frame_index.TopFrameIndexFeature()(report)(suspect).value)

  def testTopFrameIndexMiddling(self):
    """Test that the feature returns middling scores for middling indices."""
    report = self._GetDummyReport()
    suspect = self._GetMockSuspect(3)
    self.assertEqual(
        lmath.log((_MAXIMUM - 3.) / _MAXIMUM),
        top_frame_index.TopFrameIndexFeature()(report)(suspect).value)

  def testTopFrameIndexIsOverMax(self):
    """Test that we return log(0) when the top frame index is too large."""
    report = self._GetDummyReport()
    suspect = self._GetMockSuspect(_MAXIMUM + 1)
    self.assertEqual(lmath.LOG_ZERO,
        top_frame_index.TopFrameIndexFeature()(report)(suspect).value)

    suspect = self._GetMockSuspect(5)
    self.assertEqual(lmath.LOG_ZERO,
        top_frame_index.TopFrameIndexFeature(2)(report)(suspect).value)
