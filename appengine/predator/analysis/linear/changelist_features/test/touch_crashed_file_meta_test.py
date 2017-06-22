# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_report import CrashReport
from analysis.linear.changelist_features.min_distance import Distance
from analysis.linear.changelist_features.min_distance import MinDistanceFeature
from analysis.linear.changelist_features.top_frame_index import (
    TopFrameIndexFeature)
from analysis.linear.changelist_features.touch_crashed_file import (
    TouchCrashedFileFeature)
from analysis.linear.changelist_features.touch_crashed_file_meta import (
    TouchCrashedFileMetaFeature)
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


class TouchCrashedFileMetaFeatureTest(AnalysisTestCase):
  """Tests ``TouchCrashedFileMetaFeature``."""

  def setUp(self):
    super(TouchCrashedFileMetaFeatureTest, self).setUp()
    get_repository = GitilesRepository.Factory(self.GetMockHttpClient())
    min_distance_feature = MinDistanceFeature(get_repository)
    top_frame_index_feature = TopFrameIndexFeature()
    touch_crashed_file_feature = TouchCrashedFileFeature()
    self._feature = TouchCrashedFileMetaFeature(
        [min_distance_feature,
         top_frame_index_feature,
         touch_crashed_file_feature])

  def _GetDummyReport(self, deps=None, dep_rolls=None):
    crash_stack = CallStack(0, [StackFrame(0, 'src/', 'func', 'a.cc',
                                           'a.cc', [2], 'https://repo')])
    return CrashReport('rev', 'sig', 'win',
                       Stacktrace([crash_stack], crash_stack),
                       ('rev0', 'rev9'), deps, dep_rolls)

  def _GetMockSuspect(self, dep_path='src/'):
    """Returns a ``Suspect`` with the desired min_distance."""
    return Suspect(self.GetDummyChangeLog(), dep_path)

  def testAreLogZerosWhenNoMatchedFile(self):
    """Test that feature values are log(0)s when there is no matched file."""
    report = self._GetDummyReport(
        deps={'src': Dependency('src/dep', 'https://repo', '6')})
    feature_values = self._feature(report)(self._GetMockSuspect()).values()

    for feature_value in feature_values:
        self.assertEqual(0.0, feature_value.value)

  def testMinDistanceFeatureIsLogOne(self):
    """Test that the feature returns log(1) when the min_distance is 0."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    frame = StackFrame(0, 'src/', 'func', 'a.cc', 'a.cc', [2], 'https://repo')
    with mock.patch('analysis.linear.changelist_features.'
                    'min_distance.MinDistanceFeature.'
                    'DistanceBetweenTouchedFileAndFrameInfos') as mock_distance:
      mock_distance.return_value = Distance(0, frame)
      feature_values = self._feature(report)(self._GetMockSuspect())

      self.assertEqual(1.0, feature_values['MinDistance'].value)
