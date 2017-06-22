# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis import suspect_filters
from analysis.analysis_testcase import AnalysisTestCase
from analysis.suspect import Suspect


class SuspectFiltersTest(AnalysisTestCase):
  """Tests ``SuspectFilters`` classes."""

  def testFilterLessLikelySuspectsRaiseValueError(self):
    """Tests ``FilterLessLikelySuspects`` raise ValueError if negative ratio."""
    with self.assertRaises(ValueError):
      suspect_filters.FilterLessLikelySuspects(-3)

  def testFilterLessLikelySuspects(self):
    """Tests ``FilterLessLikelySuspects`` method."""
    suspect1 = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect2 = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect3 = Suspect(self.GetDummyChangeLog(), 'src/')

    suspect1.confidence = 2
    suspect2.confidence = 2
    self.assertListEqual(
        suspect_filters.FilterLessLikelySuspects(0.5)([suspect1, suspect2]),
        [])

    suspect2.confidence = 1.8
    suspect3.confidence = 1.0
    self.assertListEqual(
        suspect_filters.FilterLessLikelySuspects(0.5)([suspect1, suspect2,
                                                       suspect3]),
        [suspect1, suspect2])
