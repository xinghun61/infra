# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common.chrome_dependency_fetcher import ChromeDependencyFetcher
from common.dependency import Dependency
from common.dependency import DependencyRoll
from crash.crash_report import CrashReport
from crash.loglinear.changelist_features.touch_crashed_directory import (
    TouchCrashedDirectoryFeature)
from crash.loglinear.changelist_features.min_distance import Distance
from crash.loglinear.changelist_features.min_distance import MinDistanceFeature
from crash.loglinear.feature import ChangedFile
from crash.suspect import Suspect
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.test.predator_testcase import PredatorTestCase
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType
from libs.gitiles.gitiles_repository import GitilesRepository
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
    'commit_url': 'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '1',
    'reverted_revision': None
})


class TouchCrashedDirectoryFeatureTest(PredatorTestCase):
  """Tests ``TouchCrashedDirectoryFeature``."""

  def setUp(self):
    super(TouchCrashedDirectoryFeatureTest, self).setUp()
    self._feature = TouchCrashedDirectoryFeature()

  def testAreLogOneWhenThereIsMatchedDirectory(self):
    """Test that feature values are log(0)s when there is no matched file."""
    frame1 = StackFrame(0, 'src/', 'func', 'f.cc',
                        'src/f.cc', [2, 3], 'h://repo')
    stack = CallStack(0, frame_list=[frame1])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src/': Dependency('src/', 'h://repo', '8')}
    dep_rolls = {'src/': DependencyRoll('src/', 'h://repo', '2', '6')}
    report = CrashReport('8', 'sig', 'linux', stack_trace,
                         ('2', '6'), deps, dep_rolls)
    suspect = Suspect(_DUMMY_CHANGELOG, 'src/')
    feature_value = self._feature(report)(suspect)
    self.assertEqual(1.0, feature_value.value)

  def testMinDistanceFeatureIsLogZeroWhenNoMatchedDirectory(self):
    """Test that the feature returns log(1) when the min_distance is 0."""
    frame = StackFrame(0, 'src/', 'func', 'dir/f.cc',
                        'src/dir/f.cc', [2, 3], 'h://repo')
    stack = CallStack(0, frame_list=[frame])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src/': Dependency('src/', 'h://repo', '8')}
    dep_rolls = {'src/': DependencyRoll('src/', 'h://repo', '2', '6')}
    report = CrashReport('8', 'sig', 'linux', stack_trace,
                         ('2', '6'), deps, dep_rolls)
    suspect = Suspect(_DUMMY_CHANGELOG, 'src/')
    feature_value = self._feature(report)(suspect)
    self.assertEqual(0.0, feature_value.value)
