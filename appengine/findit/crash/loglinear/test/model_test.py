# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import numpy as np
import random
import unittest

from crash.loglinear.feature import FeatureValue
from crash.loglinear.model import ToFeatureFunction
from crash.loglinear.model import LogLinearModel


# Some arbitrary features.
# We don't use double lambdas because gpylint complains about that.
def feature0(x):
  return lambda y: FeatureValue('feature0', y == (x > 5), None, None)


def feature1(x):
  return lambda y: FeatureValue('feature1', y == ((x % 2) == 1), None, None)


def feature2(x):
  return lambda y: FeatureValue('feature2', y == (x <= 7), None, None)


features = [feature0, feature1, feature2]
X = range(10)
Y = [False, True]


class LoglinearTest(unittest.TestCase):

  def testToFeatureFunction(self):
    """Test that ``ToFeatureFunction`` obeys the equality its docstring says."""
    f = ToFeatureFunction(features)
    for x in X:
      for y in Y:
        for i in xrange(len(features)):
          self.assertEqual(features[i](x)(y), f(x)(y)[i])

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
    weights = [random.random() for _ in features]

    model = LogLinearModel(Y, ToFeatureFunction(features), weights, 0.1)
    model.ClearAllMemos()
    model = LogLinearModel(Y, ToFeatureFunction(features), weights)
    self.assertListEqual(weights, model.weights.tolist())
    self.assertEqual(math.sqrt(model.quadrance), model.l2)

    for x in X:
      self.assertEqual(math.exp(model.LogZ(x)), model.Z(x))
      model.Expectation(x, lambda y: np.array([1.0]))
      for y in Y:
        model.Features(x)(y)
        model.Score(x)(y)
        self.assertEqual(
            math.exp(model.LogProbability(x)(y)),
            model.Probability(x)(y))
