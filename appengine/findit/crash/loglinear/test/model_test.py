# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import math
import numpy as np

from crash.loglinear.feature import ChangedFile
from crash.loglinear.feature import FeatureValue
from crash.loglinear.feature import WrapperMetaFeature
from crash.loglinear.model import LogLinearModel
from crash.loglinear.model import UnnormalizedLogLinearModel
from crash.loglinear.weight import MetaWeight
from crash.loglinear.weight import Weight
from crash.loglinear.test.loglinear_testcase import LoglinearTestCase
from libs.meta_object import MetaDict


class UnnormalizedLogLinearModelTest(LoglinearTestCase):

  def setUp(self):
    super(UnnormalizedLogLinearModelTest, self).setUp()
    self.model = UnnormalizedLogLinearModel(self._meta_feature,
                                            self._meta_weight,
                                            0.00001)

  def testLogZeroish(self):
    self.assertTrue(self.model.LogZeroish(-float('inf')))
    self.assertFalse(self.model.LogZeroish(2.))

  def testFilterReasonWithWeight(self):
    meta_weight = MetaWeight({'f1': Weight(2.), 'f2': Weight(0.),
                              'f3': Weight(1.)})
    reason = MetaDict({'f1': 'reason1', 'f2': 'reason2'})

    model = UnnormalizedLogLinearModel(None, meta_weight)
    self.assertListEqual(model.FilterReasonWithWeight(reason), ['reason1'])


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
    model = LogLinearModel(self._Y, self._meta_feature, self._meta_weight)
    model.ClearAllMemos()
    self.assertEqual(self._meta_weight, model.meta_weight)
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

  def testMetaWeightSetter(self):
    model = LogLinearModel(self._Y, self._meta_feature, self._meta_weight)
    new_meta_weight = copy.deepcopy(self._meta_weight)
    new_meta_weight['Feature0'] = Weight(2.1)
    model.meta_weight = new_meta_weight
    self.assertTrue(model.meta_weight == new_meta_weight)
