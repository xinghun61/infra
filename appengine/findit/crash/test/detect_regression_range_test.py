# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from crash.detect_regression_range import GetSpikeIndexes
from crash.detect_regression_range import GetRegressionRangeFromSpike
from crash.detect_regression_range import DetectRegressionRange


class DetectRegressionRangeTest(testing.AppengineTestCase):

  def _VerifyCasesForDetectRegressonRange(self, cases):
    for case, expected_result in cases:
      result = DetectRegressionRange(case)

      self.assertEqual(result, expected_result, 'Detected spikes of %s should '
                       'be %s, instead of %s' % (repr(case),
                                                 expected_result,
                                                 result))


  def testGetSpikeIndexes(self):
    self.assertEqual(GetSpikeIndexes([]),
                     [])
    self.assertEqual(GetSpikeIndexes([('1', 0.5)]),
                     [])
    self.assertEqual(GetSpikeIndexes([('1', 0), ('2', 0.5)]),
                     [1])

  def testGetRegressionRangeFromSpike(self):
    self.assertEqual(GetRegressionRangeFromSpike(0, ['1', '2']),
                     None)
    self.assertEqual(GetRegressionRangeFromSpike(3, ['1', '2']),
                     None)
    self.assertEqual(GetRegressionRangeFromSpike(1, ['1', '2']),
                     ('1', '2'))

  def testReturnNoneForEmptyCrashData(self):
    self.assertEqual(DetectRegressionRange([]), None)

  def testReturnNoneWhenSpikeDetectionFailed(self):
    crash_history = [('1', 0), ('2', 0)]
    self.assertEqual(DetectRegressionRange(crash_history), None)

  def testDetectRegressionRangeForNewCrash(self):
    """Detect new crash that didn't happen before."""
    cases = [
        ([('1', 0), ('2', 0), ('3', 0.5)],
         ('2', '3')),
        ([('1', 0), ('2', 0), ('3', 0.1), ('4', 0.6), ('5', 0.001)],
         ('2', '3'))]

    self._VerifyCasesForDetectRegressonRange(cases)

  def testDetectRegressionRangeForStableCrash(self):
    """Detect long-existing stable crashes."""
    cases = [
        ([('1', 0.002), ('2', 0.8), ('3', 0.0007), ('4', 0.0007), ('5', 0.5)],
         ('4', '5')),
        ([('1', 0.06), ('2', 0.0003), ('3', 0.0007), ('4', 0.6), ('5', 0.002)],
         ('3', '4'))]

    self._VerifyCasesForDetectRegressonRange(cases)
