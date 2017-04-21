# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from analysis.detect_regression_range import GetSpikes
from analysis.detect_regression_range import DetectRegressionRange


class DetectRegressionRangeTest(testing.AppengineTestCase):

  def _VerifyCasesForDetectRegressonRange(self, cases):
    for case, expected_result in cases:
      result = DetectRegressionRange(case)
      self.assertEqual(result, expected_result,
          'Detected spikes of %s should be %s, instead of %s'
          % (repr(case), expected_result, result))


  # TODO(wrengr): make this test more comprehensive.
  def testGetSpikes(self):
    get_value = lambda x: x[1]
    e0 = ('1', 0.5)
    e1 = ('1', 0)
    e2 = ('2', 0.5)
    self.assertEqual(GetSpikes([], get_value),
                     [])
    self.assertEqual(GetSpikes([e0], get_value),
                     [])
    self.assertEqual(GetSpikes([e1, e2], get_value),
                     [(e1, e2)])


  def testReturnNoneForEmptyCrashData(self):
    self.assertEqual(DetectRegressionRange([]), None)

  def testReturnNoneWhenSpikeDetectionFailed(self):
    historic_metadata = [{'chrome_version': '1', 'cpm': 0},
                         {'chrome_version': '2', 'cpm': 0}]
    self.assertEqual(DetectRegressionRange(historic_metadata), None)

  def testDetectRegressionRangeForNewCrash(self):
    """Detect new crash that didn't happen before."""
    cases = [
        ([{'chrome_version': '1', 'cpm': 0},
          {'chrome_version': '2', 'cpm': 0},
          {'chrome_version': '3', 'cpm': 0.5}],
         ('2', '3')),
        ([{'chrome_version': '1', 'cpm': 0},
          {'chrome_version': '2', 'cpm': 0},
          {'chrome_version': '3', 'cpm': 0.1},
          {'chrome_version': '4', 'cpm': 0.6},
          {'chrome_version': '5', 'cpm': 0.001}],
         ('2', '3'))]

    self._VerifyCasesForDetectRegressonRange(cases)

  def testDetectRegressionRangeForStableCrash(self):
    """Detect long-existing stable crashes."""
    cases = [
        ([{'chrome_version': '1', 'cpm': 0.002},
          {'chrome_version': '2', 'cpm': 0.8},
          {'chrome_version': '3', 'cpm': 0.0007},
          {'chrome_version': '4', 'cpm': 0.0007},
          {'chrome_version': '5', 'cpm': 0.5}],
          ('4', '5')),
        ([{'chrome_version': '1', 'cpm': 0.06},
          {'chrome_version': '2', 'cpm': 0.0003},
          {'chrome_version': '3', 'cpm': 0.0007},
          {'chrome_version': '4', 'cpm': 0.6},
          {'chrome_version': '5', 'cpm': 0.002}],
         ('3', '4'))]

    self._VerifyCasesForDetectRegressonRange(cases)

