# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.callstack import StackFrame
from crash.results import MatchResult
from crash.scorers import aggregators
from crash.scorers.aggregated_scorer import AggregatedScorer
from crash.scorers.min_distance import MinDistance
from crash.scorers.test.scorer_test_suite import ScorerTestSuite
from crash.scorers.top_frame_index import TopFrameIndex


class AggregatedScorerTest(ScorerTestSuite):

  def testScore(self):
    result = MatchResult(self._GetDummyChangeLog(), 'src/', '')
    frame = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7],
                       repo_url='https://repo_url')
    result.file_to_stack_infos = {
        'a.cc': [(frame, 0)]
    }
    result.file_to_analysis_info = {
        'a.cc': {
            'min_distance': 0,
            'min_distance_frame': frame
        }
    }

    aggregator = AggregatedScorer([TopFrameIndex(), MinDistance()])
    aggregator.Score(result)

    self.assertEqual(result.confidence, 1)
    self.assertEqual(result.reasons,
                     [('TopFrameIndex', 1.0, 'Top frame is #0'),
                      ('MinDistance', 1, 'Minimum distance is 0')])
    self.assertEqual(result.changed_files,
                     [{'info': 'Minimum distance (LOC) 0, frame #0',
                       'blame_url': 'https://repo_url/+blame/1/a.cc#7',
                       'file': 'a.cc'}])

  def testScoreWithCustomizedAggregators(self):
    result = MatchResult(self._GetDummyChangeLog(), 'src/', '')
    frame = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7],
                       repo_url='https://repo_url')
    result.file_to_stack_infos = {
        'a.cc': [(frame, 0)]
    }
    result.file_to_analysis_info = {
        'a.cc': {
            'min_distance': 0,
            'min_distance_frame': frame
        }
    }

    aggregator = AggregatedScorer([TopFrameIndex(), MinDistance()])
    aggregator.Score(
        result, score_aggregator=aggregators.IdentityAggregator(),
        reasons_aggregator=aggregators.IdentityAggregator(),
        changed_files_aggregator=aggregators.ChangedFilesAggregator())

    self.assertEqual(result.confidence, [1, 1])
