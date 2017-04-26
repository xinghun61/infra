# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import numpy as np

from analysis.linear.training import TrainableLogLinearModel
from analysis.linear.linear_testcase import LinearTestCase


class TrainableLogLinearModelTest(LinearTestCase):

  def setUp(self):
    super(TrainableLogLinearModelTest, self).setUp()
    # Normally we wouldn't have *all* possible training data. But this
    # is just a test; if it doesn't work now, it'll never work.
    training_data = [(x, x == 7) for x in self._X]
    self._model = TrainableLogLinearModel(
        self._Y, training_data, self._meta_feature, self._meta_weight)

  def testNpWeightsSetterNotAnNdarray(self):
    def _NpWeightSettingExpression():
      """Wrap the ``self._model.np_weights = stuff`` expression.

      The ``assertRaises`` method expects a callable object, so we need
      to wrap the expression in a def. If we didn't wrap it in a def
      then we'd throw the exception too early, and ``assertRaises``
      would never get called in order to see it. Normally we'd use a
      lambda for wrapping the expression up, but because the expression
      we want to check is actually a statement it can't be in a lambda
      but rather must be in a def.
      """
      self._model.np_weight = 'this is not an np.ndarray'

    self.assertRaises(TypeError, _NpWeightSettingExpression)

  def testNpWeightsSetterShapeMismatch(self):

    def _WeightSettingExpression():
      """Wrap the ``self._model.weights = stuff`` expression."""
      # This np.ndarray has the wrong shape.
      self._model.np_weight = np.array([[1,2], [3,4]])

    self.assertRaises(TypeError, _WeightSettingExpression)

  def testTrainWeights(self):
    """Tests that ``TrainWeights`` actually improves the loglikelihood.

    Actually, this is more of a test that we're calling SciPy's BFGS
    implementation correctly. But any bugs we find about that will show
    up in trying to run this rest rather than in the assertaion failing
    per se.
    """
    initial_loglikelihood = self._model.LogLikelihood()
    self._model.TrainWeights(0.5)
    trained_loglikelihood = self._model.LogLikelihood()
    self.assertTrue(trained_loglikelihood >= initial_loglikelihood,
        'Training reduced the loglikelihood from %f to %f,'
        ' when it should have increased it!'
        % (initial_loglikelihood, trained_loglikelihood))
