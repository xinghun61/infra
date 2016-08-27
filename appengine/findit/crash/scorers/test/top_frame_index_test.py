# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.callstack import StackFrame
from crash.results import MatchResult
from crash.scorers.test.scorer_test_suite import ScorerTestSuite
from crash.scorers.top_frame_index import TopFrameIndex


class TopFrameIndexTest(ScorerTestSuite):

  def testGetMetric(self):
    result = MatchResult(self._GetDummyChangeLog(), 'src/', '')
    self.assertEqual(TopFrameIndex().GetMetric(result), None)

    result.file_to_stack_infos = {
        'a.cc': [(StackFrame(0, 'src/', '', 'func', 'a.cc', [7]), 0)]
    }
    self.assertEqual(TopFrameIndex().GetMetric(result), 0)

  def testScore(self):
    self.assertEqual(TopFrameIndex().Score(0), 1)
    self.assertEqual(TopFrameIndex().Score(30), 0)

  def testReason(self):
    self.assertEqual(TopFrameIndex().Reason(0, 1),
                     ('TopFrameIndex', 1, 'Top frame is #0'))
    self.assertEqual(TopFrameIndex().Reason(30, 0),
                     None)

  def testChangedFiles(self):
    result = MatchResult(self._GetDummyChangeLog(), 'src/', '')
    self.assertEqual(TopFrameIndex().ChangedFiles(result, 1), None)
