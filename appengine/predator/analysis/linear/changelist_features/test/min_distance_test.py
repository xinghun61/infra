# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_match import CrashMatch
from analysis.crash_match import FrameInfo
from analysis.crash_report import CrashReport
from analysis.linear.changelist_features import min_distance
from analysis.linear.changelist_features.touch_crashed_file_meta import (
    CrashedFile)
from analysis.linear.feature import ChangedFile
from analysis.stacktrace import CallStack
from analysis.stacktrace import ProfilerStackFrame
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from analysis.suspect import Suspect
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll
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


class DistanceTest(AnalysisTestCase):
  """Tests ``Distance`` class."""

  def testUpdate(self):
    """Tests that ``Update`` updates distance and frame."""
    distance_info = min_distance.Distance(100, None)
    distance_info.Update(50, None)
    self.assertEqual(distance_info.distance, 50)
    distance_info.Update(80, None)
    self.assertEqual(distance_info.distance, 50)

  def testIsInfinity(self):
    """Tests that ``IsInfinity`` checks if distance is infinity."""
    distance_info = min_distance.Distance(float('inf'), None)
    self.assertTrue(distance_info.IsInfinity())


class DistanceBetweenLineRangesTest(AnalysisTestCase):
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


class MinDistanceTest(AnalysisTestCase):
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
        0.0,
        min_distance.MinDistanceFeature(None, _MAXIMUM)(
            report)(suspect, {}).value)

  def testOnlyOneTouchedFilePerMatchedCrashedFile(self):
    """Test that ``CrashMatch`` can only have 1 touched file."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    frame = _MOCK_FRAME._replace(file_path='file')
    crashed = CrashedFile('file')
    matches = {
        crashed:
        CrashMatch(crashed,
                   [FileChangeInfo(ChangeType.MODIFY, 'file', 'file'),
                    FileChangeInfo(ChangeType.MODIFY, 'dummy', 'dummy')],
                   [FrameInfo(frame, 0)])
    }
    self.assertEqual(
        0.0,
        min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)(report)(
            self._GetMockSuspect(), matches).value)

  def testMinDistanceFeatureIsLogOne(self):
    """Test that the feature returns log(1) when the min_distance is 0."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    frame = _MOCK_FRAME._replace(file_path='file')
    crashed = CrashedFile('file')
    matches = {
        crashed:
        CrashMatch(crashed,
                   [FileChangeInfo(ChangeType.MODIFY, 'file', 'file')],
                   [FrameInfo(frame, 0)])
    }
    with mock.patch('analysis.linear.changelist_features.'
                    'min_distance.MinDistanceFeature.'
                    'DistanceBetweenTouchedFileAndFrameInfos') as mock_distance:
      mock_distance.return_value = min_distance.Distance(0, frame)
      self.assertEqual(
          1.0,
          min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)(
              report)(self._GetMockSuspect(), matches).value)

  def testMinDistanceFeatureMiddling(self):
    """Test that the feature returns middling scores for middling distances."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    frame = StackFrame(0, 'src/', 'func', 'f.cc', 'f.cc', [232], 'https://repo')
    distance = 42.
    crashed = CrashedFile('file')
    matches = {
        crashed:
        CrashMatch(crashed,
                   [FileChangeInfo(ChangeType.MODIFY, 'file', 'file')],
                   [FrameInfo(frame, 0)])
    }
    with mock.patch('analysis.linear.changelist_features.'
                    'min_distance.MinDistanceFeature.'
                    'DistanceBetweenTouchedFileAndFrameInfos') as mock_distance:
      mock_distance.return_value = min_distance.Distance(distance, frame)
      self.assertEqual(
          (_MAXIMUM - distance) / _MAXIMUM,
          min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)(
              report)(self._GetMockSuspect(), matches).value)

  def testMinDistanceFeatureIsOverMax(self):
    """Test that we return log(0) when the min_distance is too large."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    distance = _MAXIMUM + 1
    frame = _MOCK_FRAME._replace(file_path='file')
    crashed = CrashedFile('file')
    matches = {
        crashed:
        CrashMatch(crashed,
                   [FileChangeInfo(ChangeType.MODIFY, 'file', 'file')],
                   [FrameInfo(frame, 0)])
    }
    with mock.patch('analysis.linear.changelist_features.'
                    'min_distance.MinDistanceFeature.'
                    'DistanceBetweenTouchedFileAndFrameInfos') as mock_distance:
      mock_distance.return_value = min_distance.Distance(distance, None)
      self.assertEqual(
          0.0,
          min_distance.MinDistanceFeature(
              self._get_repository, _MAXIMUM)(report)(
              self._GetMockSuspect(), matches).value)

  def testDistanceBetweenTouchedFileAndFrameInfos(self):
    """Tests ``DistanceBetweenTouchedFileAndFrameInfos`` method."""
    feature = min_distance.MinDistanceFeature(self._get_repository, _MAXIMUM)
    frame1 = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7],
                        repo_url='https://repo_url')
    frame2 = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [17],
                        repo_url='https://repo_url')
    profiler_frame = ProfilerStackFrame(
        0, -0.1, -5.3, True, function_start_line=13)
    profiler_frame_without_line_number = ProfilerStackFrame(
        0, -0.1, -5.3, True, function_start_line=None)
    touched_file = FileChangeInfo(ChangeType.MODIFY, 'file', 'file')

    blame = Blame('rev', 'src/')
    blame.AddRegions([Region(0, 10, 'rev', 'a1', 'e1', 't1'),
                      Region(11, 20, 'dummy_rev', 'a2', 'e2', 't2')])

    url_to_blame = {'rev/file': blame}

    def _MockGetBlame(path, revision):
      revision_path = '%s/%s' % (revision, path)
      return url_to_blame.get(revision_path)

    with mock.patch('libs.gitiles.gitiles_repository.GitilesRepository.'
                    'GetBlame') as mock_get_blame:
      mock_get_blame.side_effect = _MockGetBlame

      distance_info = feature.DistanceBetweenTouchedFileAndFrameInfos(
          'rev', touched_file, [FrameInfo(frame1, 0), FrameInfo(frame2, 0)],
           Dependency('src/', 'https://repo', 'rev'))
      self.assertEqual(distance_info, min_distance.Distance(0, frame1))

      distance_info = feature.DistanceBetweenTouchedFileAndFrameInfos(
          'wrong_rev', touched_file, [FrameInfo(frame1, 0),
                                      FrameInfo(frame2, 0)],
           Dependency('src/', 'https://repo', 'wrong_rev'))
      self.assertIsNone(distance_info)

      # Test with a ProfilerStackFrame
      distance_info = feature.DistanceBetweenTouchedFileAndFrameInfos(
          'rev', touched_file,
          [FrameInfo(profiler_frame, 0),
           FrameInfo(profiler_frame_without_line_number, 0)],
           Dependency('src/', 'https://repo', 'rev'))
      self.assertEqual(distance_info, min_distance.Distance(4, profiler_frame))

      # Test that the distance remains at ``inf`` if the ProfilerStackFrames
      # passed in do not have line numbers.
      distance_info = feature.DistanceBetweenTouchedFileAndFrameInfos(
          'rev', touched_file,
           [FrameInfo(profiler_frame_without_line_number, 0)],
           Dependency('src/', 'https://repo', 'rev'))
      self.assertEqual(distance_info, min_distance.Distance(float('inf'), None))

  def testMinDistanceFeatureInfinityDistance(self):
    """Test that we return log(0) when the min_distance is infinity.

    The infinity distance means the touched file get overwritten by other
    cls, and the change didn't show in the final blame file.
    """
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})
    suspect = self._GetMockSuspect()
    crashed = CrashedFile(_MOCK_FRAME)
    matches = {
        crashed:
        CrashMatch(crashed,
                   [FileChangeInfo(ChangeType.MODIFY, 'file', 'file')],
                   [FrameInfo(_MOCK_FRAME, 0)])
    }

    with mock.patch('analysis.linear.changelist_features.min_distance.'
                    'MinDistanceFeature.'
                    'DistanceBetweenTouchedFileAndFrameInfos') as mock_distance:
      mock_distance.return_value = None
      self.assertEqual(
          0.0,
          min_distance.MinDistanceFeature(
              self._get_repository, _MAXIMUM)(report)(suspect, matches).value)

    with mock.patch('analysis.linear.changelist_features.min_distance.'
                    'MinDistanceFeature.'
                    'DistanceBetweenTouchedFileAndFrameInfos') as mock_distance:
      mock_distance.return_value = min_distance.Distance(float('inf'), None)
      self.assertEqual(
          0.0,
          min_distance.MinDistanceFeature(self._get_repository, 100)(report)(
              suspect, matches).value)

  def testMinDistanceChangedFiles(self):
    """Tests ``ChangedFile`` method."""
    report = self._GetDummyReport(
        deps={'src/': Dependency('src/', 'https://repo', '6')},
        dep_rolls={'src/': DependencyRoll('src/', 'https://repo', '0', '4')})

    distance = 42
    crashed = CrashedFile(_MOCK_FRAME)
    matches = {
        crashed:
        CrashMatch(crashed,
                   [FileChangeInfo(ChangeType.MODIFY, 'file', 'file')],
                   [FrameInfo(_MOCK_FRAME, 0)])
    }
    frame = StackFrame(0, 'src/', 'func', 'f.cc', 'f.cc', [7], 'https://repo')
    with mock.patch('analysis.linear.changelist_features.min_distance.'
                    'MinDistanceFeature.'
                    'DistanceBetweenTouchedFileAndFrameInfos') as mock_distance:
      mock_distance.return_value = min_distance.Distance(distance, frame)
      self.assertEqual(
          min_distance.MinDistanceFeature(
              self._get_repository, _MAXIMUM)(report)(
              self._GetMockSuspect(), matches).changed_files,
              [ChangedFile(name='file',
                           blame_url=('%s/+blame/%s/f.cc#%d' %
                                      (frame.repo_url,
                                       report.crashed_version,
                                       frame.crashed_line_numbers[0])),
                           reasons=['Distance between touched lines and'
                                    ' stacktrace lines is %d, in frame #%d'
                                    % (distance, frame.index)])])
