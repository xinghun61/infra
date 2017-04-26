# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random
import unittest

from analysis.linear.feature import ChangedFile
from analysis.linear.feature import Feature
from analysis.linear.feature import FeatureValue
from analysis.linear.feature import MetaFeature
from analysis.linear.feature import MetaFeatureValue
from analysis.linear.feature import WrapperMetaFeature
from analysis.linear.weight import MetaWeight
from analysis.linear.weight import Weight

# Some arbitrary features.
class Feature0(Feature):  # pragma: no cover
  @property
  def name(self):
    return 'Feature0'

  def __call__(self, x):
    return lambda y: FeatureValue(self.name, y == (x > 5), 'reason0',
                                  [ChangedFile(name='a.cc',
                                               blame_url=None,
                                               reasons=['file_reason0']),
                                   ChangedFile(name='b.cc',
                                               blame_url=None,
                                               reasons=['file_reason0'])])


class Feature1(Feature):  # pragma: no cover
  @property
  def name(self):
    return 'Feature1'

  def __call__(self, x):
    return lambda y: FeatureValue(self.name, y == ((x % 2) == 1), 'reason1',
                                  [ChangedFile(name='b.cc',
                                               blame_url=None,
                                               reasons=['file_reason1'])])


class Feature2(Feature):  # pragma: no cover
  @property
  def name(self):
    return 'Feature2'

  def __call__(self, x):
    return lambda y: FeatureValue(self.name, y == (x <= 7), 'reason2', None)


class Feature3(Feature):  # pragma: no cover
  @property
  def name(self):
    return 'Feature3'

  def __call__(self, x):
    return lambda y: FeatureValue(self.name, y == ((x % 3) == 0), None, None)


class Feature4(Feature):  # pragma: no cover
  @property
  def name(self):
    return 'Feature4'

  def __call__(self, x):
    return lambda y: FeatureValue(self.name, y == (x < 9), None, None)


class LinearTestCase(unittest.TestCase):  # pragma: no cover
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
    super(LinearTestCase, self).setUp()

    self._meta_feature = WrapperMetaFeature([Feature0(),
                                             Feature1(),
                                             Feature2(),
                                             WrapperMetaFeature([Feature3(),
                                                                 Feature4()])])
    self._meta_weight = MetaWeight(
        {
            'Feature0': Weight(random.random()),
            'Feature1': Weight(random.random()),
            'Feature2': Weight(random.random()),
            'WrapperFeature': MetaWeight(
                {
                    'Feature3': Weight(random.random()),
                    'Feature4': Weight(random.random())
                })
         })

    self._X = range(10)
    self._Y = lambda _x: [False, True]
