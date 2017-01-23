# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import numpy as np

from crash.loglinear.feature import ChangedFile
from crash.loglinear.feature import FeatureValue
from crash.loglinear.feature import FeatureFunction
from crash.loglinear.model import LogLinearModel
from crash.loglinear.model import UnnormalizedLogLinearModel
from crash.loglinear.test.loglinear_testcase import LoglinearTestCase


class UnnormalizedLogLinearModelTest(LoglinearTestCase):

  def setUp(self):
    super(UnnormalizedLogLinearModelTest, self).setUp()
    self.model = UnnormalizedLogLinearModel(self._feature_function,
                                            self._weights)

  def testSingleFeatureScore(self):
    """Test that ``SingleFeatureScore`` returns weighted feature score."""
    for feature in self._feature_list:
      feature_value = feature(5)(True)
      self.assertEqual(
          self.model.SingleFeatureScore(feature_value),
          feature_value.value * self.model._weights.get(feature_value.name, 0.))

  def testFormatReasons(self):
    """Tests ``FormatReasons`` returnes a list of formated reasons."""
    features = [feature(3)(False) for feature in self._feature_list]
    self.assertListEqual([(feature.name, self.model.SingleFeatureScore(feature),
                           feature.reason) for feature in features],
                         self.model.FormatReasons(features))

  def testAggregateChangedFilesAggregates(self):
    """Test that ``AggregateChangedFiles`` does aggregate reasons per file.

    In the main/inner loop of ``AggregateChangedFiles``: if multiple
    features all blame the same file change, we try to aggregate those
    reasons so that we only report the file once (with all reasons). None
    of the other tests here actually check the case where the same file
    is blamed multiple times, so we check that here.

    In particular, we provide the same ``FeatureValue`` twice, and
    hence the same ``ChangedFile`` twice; so we should get back a single
    ``ChangedFile`` but with the ``reasons`` fields concatenated.
    """
    file_reason = 'I blame you!'
    file_blame = ChangedFile(
        name = 'a.cc',
        blame_url = None,
        reasons = [file_reason]
    )

    feature_value = FeatureValue(
        name = 'dummy feature',
        value = 42,
        reason = 'dummy reason',
        changed_files = [file_blame]
    )

    expected_file_blame = file_blame._replace(reasons = [file_reason] * 2)

    self.assertListEqual(
        [expected_file_blame],
         self.model.AggregateChangedFiles([feature_value] * 2))


class LoglinearTest(LoglinearTestCase):

  def testLogLinearModel(self):
    """An arbitrary test to get 100% code coverage.

    Right now this test simply calls every method. The only assertions are
    that log-domain and normal-domain things are related appropriately;
    and similarly for the quadrance and l2-norm. Since the one is defined
    in terms of the other in exactly the way written here, those should
    be trivially true. However, if the implementation changes, then they
    may become flaky due to floating point fuzz. Really this should be
    replaced by a collection of semantically meaningful tests, i.e.,
    ones that actually look for bugs we might realistically need to
    guard against. At least this test is good for detecting typo-style
    errors where we try accessing fields/methods that don't exist.
    """
    model = LogLinearModel(self._Y, self._feature_function, self._weights, 0.1)
    model.ClearAllMemos()
    model = LogLinearModel(self._Y, self._feature_function, self._weights)
    self.assertDictEqual(self._weights, model.weights)
    self.assertEqual(math.sqrt(model.quadrance), model.l2)

    for x in self._X:
      self.assertEqual(math.exp(model.LogZ(x)), model.Z(x))
      model.Expectation(x, lambda y: np.array([1.0]))
      for y in self._Y(x):
        model.Features(x)(y)
        model.Score(x)(y)
        self.assertEqual(
            math.exp(model.LogProbability(x)(y)),
            model.Probability(x)(y))
