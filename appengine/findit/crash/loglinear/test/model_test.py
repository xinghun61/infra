# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import numpy as np

from crash.loglinear.model import ToFeatureFunction
from crash.loglinear.model import LogLinearModel
from crash.loglinear.test.loglinear_testcase import LoglinearTestCase


class LoglinearTest(LoglinearTestCase):

  def testToFeatureFunction(self):
    """Test that ``ToFeatureFunction`` obeys the equality its docstring says."""
    for x in self._X:
      for y in self._Y:
        for i in xrange(self._qty_features):
          self.assertEqual(self._feature_list[i](x)(y),
                           self._feature_function(x)(y)[i])

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
    self.assertListEqual(self._weights, model.weights.tolist())
    self.assertEqual(math.sqrt(model.quadrance), model.l2)

    for x in self._X:
      self.assertEqual(math.exp(model.LogZ(x)), model.Z(x))
      model.Expectation(x, lambda y: np.array([1.0]))
      for y in self._Y:
        model.Features(x)(y)
        model.Score(x)(y)
        self.assertEqual(
            math.exp(model.LogProbability(x)(y)),
            model.Probability(x)(y))
