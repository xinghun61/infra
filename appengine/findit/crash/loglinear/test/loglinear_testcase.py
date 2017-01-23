# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random
import unittest

from crash.loglinear.feature import Feature
from crash.loglinear.feature import FeatureFunction
from crash.loglinear.feature import FeatureValue


# Some arbitrary features.
class Feature0(Feature):  # pragma: no cover
  @property
  def name(self):
    return 'feature0'

  def __call__(self, x):
    return lambda y: FeatureValue('feature0', y == (x > 5), 'reason0', None)

class Feature1(Feature):  # pragma: no cover
  @property
  def name(self):
    return 'feature1'

  def __call__(self, x):
    return lambda y: FeatureValue('feature1', y == ((x % 2) == 1),
                                  'reason1', None)

class Feature2(Feature):  # pragma: no cover
  @property
  def name(self):
    return 'feature2'

  def __call__(self, x):
    return lambda y: FeatureValue('feature2', y == (x <= 7), 'reason2', None)


class LoglinearTestCase(unittest.TestCase):  # pragma: no cover
  """Common code for testing ``model.py`` and ``training.py``."""

  def setUp(self):
    """Set up some basic parts of our loglinear model.

    These parts describe a silly model for detecting whether an integer
    in [0..9] is the number 7. So ``X`` is the set of integers [0..9],
    and ``Y`` is the set of ``bool`` values. The independent variable
    is boolean-valued because we only have two categories: "yes, x ==
    7" and "no, x != 7". This doesn't take advantage of the fact that
    loglinear models can categorize larger sets of labels, but it's good
    enough for testing purposes.

    In addition to specifying ``X`` and ``Y``, we also specify a set of
    features and choose some random weights for them.
    """
    super(LoglinearTestCase, self).setUp()

    self._feature_list = [Feature0(), Feature1(), Feature2()]
    self._feature_function = FeatureFunction(self._feature_list)
    self._qty_features = len(self._feature_list)
    self._X = range(10)
    self._Y = lambda _x: [False, True]
    self._weights = {feature.name: random.random()
                     for feature in self._feature_list}
