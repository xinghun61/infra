# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import unittest

from analysis.linear import feature
from analysis.linear.feature import ChangedFile
from analysis.linear.feature import MetaFeatureValue
from analysis.linear.linear_testcase import Feature0
from analysis.linear.linear_testcase import Feature1
from analysis.linear.linear_testcase import Feature2
from analysis.linear.linear_testcase import Feature3
from analysis.linear.linear_testcase import Feature4
from analysis.linear.linear_testcase import LinearTestCase
import libs.math.logarithms as lmath
from libs.meta_object import MetaDict

_MAXIMUM = 50.


class ChangelistFeatureTest(unittest.TestCase):

  def testLinearlyScaledIsZero(self):
    """Test that ``LinearlyScaled`` takes 0 to 1."""
    self.assertEqual(1., feature.LinearlyScaled(0., _MAXIMUM))

  def testLinearlyScaledMiddling(self):
    """Test that ``LinearlyScaled`` takes middling values to middling values."""
    self.assertEqual((_MAXIMUM - 42.) / _MAXIMUM,
        feature.LinearlyScaled(42., _MAXIMUM))

  def testLinearlyScaledIsOverMax(self):
    """Test that ``LinearlyScaled`` takes values over the max to 0."""
    self.assertEqual(0., feature.LinearlyScaled(42., 10.))

  def testLogLinearlyScaledIsZero(self):
    """Test that ``LogLinearlyScaled`` takes log(0) to log(1)."""
    self.assertEqual(lmath.LOG_ONE, feature.LogLinearlyScaled(0., _MAXIMUM))

  def testLogLinearlyScaledMiddling(self):
    """Test that ``LogLinearlyScaled`` works on middling values."""
    self.assertEqual(
        lmath.log((_MAXIMUM - 42.) / _MAXIMUM),
        feature.LogLinearlyScaled(42., _MAXIMUM))

  def testLogLinearlyScaledIsOverMax(self):
    """Test that ``LogLinearlyScaled`` takes values over the max to log(0)."""
    self.assertEqual(lmath.LOG_ZERO, feature.LogLinearlyScaled(42., 10.))


class MetaFeatureValueTest(unittest.TestCase):

  def setUp(self):
    super(MetaFeatureValueTest, self).setUp()
    self.feature = MetaFeatureValue(
        'dummy', {feature.name: feature(3)(False)
                  for feature in [Feature0(), Feature1(), Feature3()]})

  def testEqaul(self):
    """Tests overriding ``__eq__`` and ``__ne__``."""
    copy_meta_feature = copy.deepcopy(self.feature)
    self.assertTrue(self.feature == copy_meta_feature)
    copy_meta_feature._name = 'dummy2'
    self.assertTrue(self.feature != copy_meta_feature)

  def testLen(self):
    """Tests overriding ``__len__``."""
    self.assertEqual(len(self.feature), 3)

  def testFormatReasons(self):
    """Tests ``FormatReasons`` returnes a list of formated reasons."""
    feature0 = Feature0()
    feature1 = Feature1()
    feature2 = Feature2()
    meta_feature = MetaFeatureValue(
        'dummy',
        {feature0.name: feature0(1)(False),
         'meta': MetaFeatureValue(
             'meta',
             {feature1.name: feature1(2)(True),
              feature2.name: feature2(3)(True)})})
    self.assertEqual(meta_feature.reason, {'Feature0': 'reason0',
                                           'Feature1': 'reason1',
                                           'Feature2': 'reason2'})
    self.assertEqual(meta_feature.reason, meta_feature._reason)

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
    self.assertListEqual(self.feature.changed_files,
                         [ChangedFile(name='a.cc',
                                      blame_url=None,
                                      reasons=['file_reason0']),
                          ChangedFile(name='b.cc',
                                      blame_url=None,
                                      reasons=['file_reason0',
                                               'file_reason1'])])
    self.assertEqual(self.feature.changed_files,
                     self.feature._changed_files)


class WrapperMetaFeatureTest(LinearTestCase):

  def testWrapperMetaFeatureWrapsIndependentFeatures(self):
    for x in self._X:
      for y in self._Y(x):
        self.assertTrue(
            self._meta_feature(x)(y) ==
            MetaFeatureValue('WrapperFeature',
                             {'Feature0': Feature0()(x)(y),
                              'Feature1': Feature1()(x)(y),
                              'Feature2': Feature2()(x)(y),
                              'WrapperFeature': MetaFeatureValue(
                                  'WrapperFeature',
                                  {'Feature3': Feature3()(x)(y),
                                   'Feature4': Feature4()(x)(y)})}))
