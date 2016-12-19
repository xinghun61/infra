# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.stacktrace import StackFrame
from crash.suspect import AnalysisInfo
from crash.suspect import Suspect
from crash.suspect import StackInfo
from crash.scorers import aggregators
from crash.scorers.aggregated_scorer import AggregatedScorer
from crash.scorers.min_distance import MinDistance
from crash.scorers.test.scorer_test_suite import ScorerTestSuite
from crash.scorers.top_frame_index import TopFrameIndex


class AggregatedScorerTest(ScorerTestSuite):

  def testScore(self):
    suspect = Suspect(self._GetDummyChangeLog(), 'src/')
    frame = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7],
                       repo_url='https://repo_url')
    suspect.file_to_stack_infos = {
        'a.cc': [StackInfo(frame, 0)]
    }
    suspect.file_to_analysis_info = {
        'a.cc': AnalysisInfo(
            min_distance=0,
            min_distance_frame=frame
        )
    }

    aggregator = AggregatedScorer([TopFrameIndex(), MinDistance()])
    aggregator.Score(suspect)

    self.assertEqual(suspect.confidence, 1)
    self.assertEqual(suspect.reasons,
                     [('TopFrameIndex', 1.0, 'Top frame is #0'),
                      ('MinDistance', 1, 'Minimum distance is 0')])
    self.assertEqual(suspect.changed_files,
                     [{'info': 'Minimum distance (LOC) 0, frame #0',
                       'blame_url': 'https://repo_url/+blame/1/a.cc#7',
                       'file': 'a.cc'}])

  def testScoreWithCustomizedAggregators(self):
    suspect = Suspect(self._GetDummyChangeLog(), 'src/')
    frame = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7],
                       repo_url='https://repo_url')
    suspect.file_to_stack_infos = {
        'a.cc': [(frame, 0)]
    }
    suspect.file_to_analysis_info = {
        'a.cc': AnalysisInfo(
            min_distance=0,
            min_distance_frame=frame
        )
    }

    aggregator = AggregatedScorer([TopFrameIndex(), MinDistance()])
    aggregator.Score(
        suspect, score_aggregator=aggregators.IdentityAggregator(),
        reasons_aggregator=aggregators.IdentityAggregator(),
        changed_files_aggregator=aggregators.ChangedFilesAggregator())

    self.assertEqual(suspect.confidence, [1, 1])
