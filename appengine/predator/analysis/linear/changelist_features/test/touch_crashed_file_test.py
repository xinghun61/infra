# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_match import CrashMatch
from analysis.crash_match import FrameInfo
from analysis.linear.changelist_features.touch_crashed_file import (
    TouchCrashedFileFeature)
from analysis.linear.changelist_features.touch_crashed_file_meta import (
    CrashedFile)
from analysis.stacktrace import StackFrame
from analysis.suspect import Suspect
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType
import libs.math.logarithms as lmath


class TouchCrashedFileFeatureTest(AnalysisTestCase):
  """Tests ``TouchCrashedFileFeature``."""

  def _GetDummyReport(self):
    return None

  def _GetMockSuspect(self):
    return Suspect(self.GetDummyChangeLog(), 'src/')

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
