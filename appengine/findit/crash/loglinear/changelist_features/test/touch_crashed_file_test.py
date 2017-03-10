# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from crash.crash_match import CrashMatch
from crash.crash_match import FrameInfo
from crash.loglinear.changelist_features.touch_crashed_file import (
    TouchCrashedFileFeature)
from crash.loglinear.changelist_features.touch_crashed_file_meta import (
    CrashedFile)
from crash.stacktrace import StackFrame
from crash.suspect import Suspect
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType
import libs.math.logarithms as lmath


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


class TouchCrashedFileFeatureTest(unittest.TestCase):
  """Tests ``TouchCrashedFileFeature``."""

  def _GetDummyChangeLog(self):
    return _DUMMY_CHANGELOG

  def _GetDummyReport(self):
    return None

  def _GetMockSuspect(self):
    return Suspect(self._GetDummyChangeLog(), 'src/')

  def testIsLogZeroWhenThereIsNoMatchedFiles(self):
    """Test that the feature returns log(0) when there is no matched file."""
    report = self._GetDummyReport()
    suspect = self._GetMockSuspect()
    self.assertEqual(0.0,
                     TouchCrashedFileFeature()(report)(suspect, {}).value)

  def testIsLogOneWhenThereIsMatchedFiles(self):
    """Test that the feature returns log(1) when there is matched file."""
    report = self._GetDummyReport()
    suspect = self._GetMockSuspect()
    frame = StackFrame(index=0,
                       dep_path=suspect.dep_path,
                       function='func',
                       file_path='a.cc',
                       raw_file_path='a.cc',
                       crashed_line_numbers=[7])

    crashed = CrashedFile(frame)
    matches = {crashed:
               CrashMatch(crashed,
                          [FileChangeInfo(ChangeType.MODIFY, 'a.cc', 'a.cc')],
                          [FrameInfo(frame=frame, priority = 0)])}
    self.assertEqual(1.0,
                     TouchCrashedFileFeature()(report)(suspect, matches).value)
