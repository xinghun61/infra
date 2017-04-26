# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_report import CrashReport
from analysis.linear.changelist_features.touch_crashed_directory import (
    TouchCrashedDirectoryFeature)
from analysis.linear.changelist_features.min_distance import Distance
from analysis.linear.changelist_features.min_distance import MinDistanceFeature
from analysis.linear.feature import ChangedFile
from analysis.suspect import Suspect
from analysis.stacktrace import CallStack
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType
from libs.gitiles.gitiles_repository import GitilesRepository
import libs.math.logarithms as lmath


class TouchCrashedDirectoryFeatureTest(AnalysisTestCase):
  """Tests ``TouchCrashedDirectoryFeature``."""

  def setUp(self):
    super(TouchCrashedDirectoryFeatureTest, self).setUp()
    self._feature = TouchCrashedDirectoryFeature()

  def testFeatureValueIsOneWhenThereIsMatchedDirectory(self):
    """Test that feature value is 1 when there is matched directory."""
    frame1 = StackFrame(0, 'src/', 'func', 'p/f.cc',
                        'src/p/f.cc', [2, 3], 'h://repo')
    stack = CallStack(0, frame_list=[frame1])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src/': Dependency('src/', 'h://repo', '8')}
    dep_rolls = {'src/': DependencyRoll('src/', 'h://repo', '2', '6')}
    report = CrashReport('8', 'sig', 'linux', stack_trace,
                         ('2', '6'), deps, dep_rolls)
    changelog = self.GetDummyChangeLog()._replace(
        touched_files=[FileChangeInfo.FromDict({
            'change_type': 'add',
            'new_path': 'p/a.cc',
            'old_path': None,
        })])
    suspect = Suspect(changelog, 'src/')
    feature_value = self._feature(report)(suspect)
    self.assertEqual(1.0, feature_value.value)

  def testFeatureValueIsZeroWhenNoMatchedDirectory(self):
    """Test that the feature returns 0 when there no matched directory."""
    frame = StackFrame(0, 'src/', 'func', 'dir/f.cc',
                        'src/dir/f.cc', [2, 3], 'h://repo')
    stack = CallStack(0, frame_list=[frame])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src/': Dependency('src/', 'h://repo', '8')}
    dep_rolls = {'src/': DependencyRoll('src/', 'h://repo', '2', '6')}
    report = CrashReport('8', 'sig', 'linux', stack_trace,
                         ('2', '6'), deps, dep_rolls)
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    feature_value = self._feature(report)(suspect)
    self.assertEqual(0.0, feature_value.value)
