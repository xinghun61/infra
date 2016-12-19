# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.stacktrace import StackFrame
from crash.suspect import Suspect
from crash.scorers import aggregators
from crash.scorers.min_distance import MinDistance
from crash.scorers.test.scorer_test_suite import ScorerTestSuite
from crash.scorers.top_frame_index import TopFrameIndex


class AggregatorsTest(ScorerTestSuite):

  def testMultiplier(self):
    aggregator = aggregators.Multiplier()
    self.assertEqual(aggregator.Aggregate([1, 0.5, 0.2]), 0.1)
    self.assertEqual(aggregator([None, None]), None)
    self.assertEqual(aggregator([1, 0.5, 0.2]), 0.1)

  def testIdentityAggregator(self):
    aggregator = aggregators.IdentityAggregator()
    self.assertEqual(aggregator.Aggregate([1, 0.5, 0.2]), [1, 0.5, 0.2])
    self.assertEqual(aggregator([1, 0.5, 0.2]), [1, 0.5, 0.2])

  def testChangedFilesAggregator(self):
    aggregator = aggregators.ChangedFilesAggregator()
    file_info_list = [
        [
            {'file': 'f1.cc', 'blame_url': 'https://repo_url',
             'info': 'scorer 1'},
            {'file': 'f2.cc', 'blame_url': 'https://repo_url',
             'info': 'scorer 1'},
        ],
         [
            {'file': 'f1.cc', 'blame_url': 'https://repo_url',
             'info': None},
            {'file': 'f2.cc', 'blame_url': 'https://repo_url',
             'info': 'scorer 2'},
        ],
    ]
    self.assertEqual(aggregator(file_info_list),
                     [{'file': 'f1.cc', 'blame_url': 'https://repo_url',
                       'info': 'scorer 1'},
                      {'file': 'f2.cc', 'blame_url': 'https://repo_url',
                       'info': 'scorer 1\nscorer 2'}])


