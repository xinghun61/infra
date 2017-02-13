# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common.chrome_dependency_fetcher import ChromeDependencyFetcher
from common.dependency import Dependency
from common.dependency import DependencyRoll
from crash.crash_report import CrashReport
from crash.loglinear.changelist_features import min_distance
from crash.loglinear.feature import ChangedFile
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.suspect import AnalysisInfo
from crash.suspect import Suspect
from crash.suspect import StackInfo
from crash.test.predator_testcase import PredatorTestCase
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType
from libs.gitiles.gitiles_repository import GitilesRepository
import libs.math.logarithms as lmath


_MAXIMUM = 50

_MOCK_FRAME = StackFrame(0, 'src/', 'func', 'f.cc', 'a/b/src/f.cc', [2],
                         repo_url='https://repo_url')
_MOCK_FRAME2 = StackFrame(0, 'src/', 'func', 'f.cc', 'a/b/src/ff.cc', [22],
                         repo_url='https://repo_url')

class ModifiedFrameInfoTest(unittest.TestCase):
  """Tests ``ModifiedFrameInfo`` class."""

  def testUpdate(self):
    """Tests that ``Update`` updates distance and frame."""
    distance_info = min_distance.ModifiedFrameInfo(100, None)
    distance_info.Update(50, None)
    self.assertEqual(distance_info.distance, 50)
    distance_info.Update(80, None)
    self.assertEqual(distance_info.distance, 50)

  def testIsInfinity(self):
    """Tests that ``IsInfinity`` checks if distance is infinity."""
    distance_info = min_distance.ModifiedFrameInfo(float('inf'), None)
    self.assertTrue(distance_info.IsInfinity())


class DistanceBetweenLineRangesTest(unittest.TestCase):
  """Tests ``DistanceBetweenLineRanges`` function."""

  def testDistanceBetweenLineRanges(self):
    """Tests that the function computes distance between 2 line ranges."""
    self.assertEqual(min_distance.DistanceBetweenLineRanges((1, 10), (3, 9)), 0)
    self.assertEqual(min_distance.DistanceBetweenLineRanges((1, 2), (6, 9)), 4)

  def testRaisesException(self):
    """Tests that the function raises exception when line range is invalid."""
    self.assertRaises(ValueError,
                      min_distance.DistanceBetweenLineRanges, (6, 2), (1, 4))
    self.assertRaises(ValueError,
                      min_distance.DistanceBetweenLineRanges, (2, 6), (4, 1))


class MinDistanceTest(PredatorTestCase):
  """Tests ``MinDistanceFeature``."""

  def setUp(self):
    super(MinDistanceTest, self).setUp()
    self._get_repository = GitilesRepository.Factory(self.GetMockHttpClient())

  def _GetDummyReport(self, deps=None, dep_rolls=None):
    """Gets dummy ``CrashReport``."""
    crash_stack = CallStack(0, [StackFrame(0, 'src/', 'func', 'f.cc',
                                           'f.cc', [232], 'https://repo')])
    return CrashReport('rev', 'sig', 'win',
                       Stacktrace([crash_stack], crash_stack),
                       ('rev0', 'rev9'), deps, dep_rolls)

  def _GetMockSuspect(self, dep_path='src/'):
    """Returns a dummy ``Suspect``."""
    return Suspect(self.GetDummyChangeLog(), dep_path)

  def testMinDistanceFeatureIsLogZero(self):
    """Test that the feature returns log(0) when there are no matched files."""
    report = self._GetDummyReport()
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    self.assertEqual(
        lmath.LOG_ZERO,
        min_distance.MinDistanceFeature(None, _MAXIMUM)(
            report)(suspect, {}).value)

  def testMinDistanceFeatureIsLogOne(self):
    """Test that the feature returns log(1) when the min_distance is 0."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    touched_file_to_stack_infos = {
        FileChangeInfo(ChangeType.MODIFY, 'file', 'file'):
        [StackInfo(_MOCK_FRAME, 0)]
    }
    self.mock(min_distance.MinDistanceFeature,
              'DistanceBetweenTouchedFileAndStacktrace',
              lambda *_: min_distance.ModifiedFrameInfo(0, None))
    self.assertEqual(
        lmath.LOG_ONE,
        min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)(report)(
            self._GetMockSuspect(), touched_file_to_stack_infos).value)

  def testMinDistanceFeatureMiddling(self):
    """Test that the feature returns middling scores for middling distances."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    frame = StackFrame(0, 'src/', 'func', 'f.cc', 'f.cc', [232], 'https://repo')
    distance = 42.
    touched_file_to_stack_infos = {
        FileChangeInfo(ChangeType.MODIFY, 'file', 'file'):
        [StackInfo(frame, 0)]
    }
    self.mock(min_distance.MinDistanceFeature,
              'DistanceBetweenTouchedFileAndStacktrace',
              lambda *_: min_distance.ModifiedFrameInfo(distance, frame))
    self.assertEqual(
        lmath.log((_MAXIMUM - distance) / _MAXIMUM),
        min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)(report)(
            self._GetMockSuspect(), touched_file_to_stack_infos).value)

  def testMinDistanceFeatureIsOverMax(self):
    """Test that we return log(0) when the min_distance is too large."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    distance = _MAXIMUM + 1
    touched_file_to_stack_info = {
        FileChangeInfo(ChangeType.MODIFY, 'file', 'file'):
        AnalysisInfo(
            min_distance=distance,
            min_distance_frame=_MOCK_FRAME)
    }
    self.mock(min_distance.MinDistanceFeature,
              'DistanceBetweenTouchedFileAndStacktrace',
              lambda *_: min_distance.ModifiedFrameInfo(distance, None))
    self.assertEqual(
        lmath.log((_MAXIMUM - distance) / _MAXIMUM),
        min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)(report)(
            self._GetMockSuspect(), touched_file_to_stack_info).value)

  def testDistanceBetweenTouchedFileAndStacktrace(self):
    """Tests ``DistanceBetweenTouchedFileAndStacktrace`` method."""
    feature = min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)
    frame1 = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7],
                        repo_url='https://repo_url')
    frame2 = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [17],
                        repo_url='https://repo_url')
    touched_file = FileChangeInfo(ChangeType.MODIFY, 'file', 'file')

    blame = Blame('rev', 'src/')
    blame.AddRegions([Region(0, 10, 'rev', 'a1', 'e1', 't1'),
                      Region(11, 20, 'dummy_rev', 'a2', 'e2', 't2')])

    url_to_blame = {'rev/file': blame}

    def _MockGetBlame(_, path, revision):
      revision_path = '%s/%s' % (revision, path)
      return url_to_blame.get(revision_path)

    self.mock(GitilesRepository, 'GetBlame', _MockGetBlame)

    distance_info = feature.DistanceBetweenTouchedFileAndStacktrace(
        'rev', touched_file, [StackInfo(frame1, 0), StackInfo(frame2, 0)],
         Dependency('src/', 'https://repo', 'rev'))
    self.assertEqual(distance_info, min_distance.ModifiedFrameInfo(0, frame1))

    distance_info = feature.DistanceBetweenTouchedFileAndStacktrace(
        'wrong_rev', touched_file, [StackInfo(frame1, 0), StackInfo(frame2, 0)],
         Dependency('src/', 'https://repo', 'wrong_rev'))
    self.assertIsNone(distance_info)

  def testMinDistanceFeatureInfinityDistance(self):
    """Test that we return log(0) when the min_distance is infinity.

    The infinity distance means the touched file get overwritten by other
    cls, and the change didn't show in the final blame file.
    """
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})
    suspect = self._GetMockSuspect()

    distance = _MAXIMUM + 1
    touched_file_to_stack_info = {
        FileChangeInfo(ChangeType.MODIFY, 'file', 'file'):
        AnalysisInfo(
            min_distance=distance,
            min_distance_frame=_MOCK_FRAME)
    }
    self.mock(min_distance.MinDistanceFeature,
              'DistanceBetweenTouchedFileAndStacktrace',
              lambda *_: None)
    self.assertEqual(
        lmath.LOG_ZERO,
        min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)(report)(
            suspect, touched_file_to_stack_info).value)
    self.mock(min_distance.MinDistanceFeature,
              'DistanceBetweenTouchedFileAndStacktrace',
              lambda *_: min_distance.ModifiedFrameInfo(float('inf'), None))
    self.assertEqual(
        lmath.LOG_ZERO,
        min_distance.MinDistanceFeature(self._get_repository, 100)(report)(
            suspect, touched_file_to_stack_info).value)

  def testMinDistanceChangedFiles(self):
    """Tests ``ChangedFile`` method."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    distance = 42
    touched_file_to_stack_info = {
        FileChangeInfo(ChangeType.MODIFY, 'file', 'file'):
        AnalysisInfo(
            min_distance=distance,
            min_distance_frame=_MOCK_FRAME)
    }
    frame = StackFrame(0, 'src/', 'func', 'f.cc', 'f.cc', [7], 'https://repo')
    self.mock(min_distance.MinDistanceFeature,
              'DistanceBetweenTouchedFileAndStacktrace',
              lambda *_: min_distance.ModifiedFrameInfo(distance, frame))
    self.assertEqual(
        min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)(report)(
            self._GetMockSuspect(), touched_file_to_stack_info).changed_files,
            [ChangedFile(name='file',
                         blame_url=('%s/+blame/%s/f.cc#%d' %
                                    (frame.repo_url,
                                     report.crashed_version,
                                     frame.crashed_line_numbers[0])),
                         reasons=['Distance from touched lines and crashed '
                                  'lines is %d, in frame #%d' % (
                                      distance, frame.index)])])
