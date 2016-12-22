# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import numpy as np
# N.B., ``np.array`` can't take generators; you must pass explicit lists.
import scipy.optimize as spo

from crash.loglinear.model import LogLinearModel
from libs.math.vectors import vsum
# N.B., ``vsum`` can't take generators; you must pass explicit lists.


class TrainableLogLinearModel(LogLinearModel):
  """A loglinear model with some labelled data set for training the weights."""

  def __init__(self, Y, training_data, feature_function, initial_weights,
               epsilon=None):
    """
    Args:
      Y (iterable): the entire range of values for the independent
        variable. This is needed for computing the partition function.
      training_data (iterable): a collection of ``(x, y)`` pairs where
        ``y`` is the known-correct label for ``x``.
      feature_function: A function from ``X`` to ``Y`` to a list of
        ``float``. N.B., the length of the list must be the same for all
        ``x`` and ``y``, and must be the same as the length of the list
        of weights.
      initial_weights (list of float): the pre-training coefficients
        for how much we believe components of the feature vector. This
        provides the seed for training; this starting value shouldn't
        affect the final weights obtained by training (thanks to
        convexity), but will affect how long it takes for training
        to converge.
      epsilon (float): The absolute-error threshold for considering a
        weight to be "equal to zero". N.B., this should be a positive
        number, as we will compare it against the absolute value of
        each weight.
    """
    super(TrainableLogLinearModel, self).__init__(
        Y, feature_function, initial_weights, epsilon)
    self._training_data = training_data

    self._observed_feature_vector = vsum([
        self.FeaturesAsNumPyArray(x)(y)
        for x, y in self._training_data])

  # Even though this is identical to the superclass definition, we must
  # re-provide it in order to define the setter.
  @property
  def weights(self):
    """The weight covector.

    At present we return the weights as an ``np.ndarray``, but in the
    future that may be replaced by a more general type which specifies
    the semantics rather than the implementation details.
    """
    return self._weights

  @weights.setter
  def weights(self, new_weights): # pylint: disable=W0221
    """Mutate the weight covector, and clear memos as necessary.

    This setter attempts to avoid clearing memos whenever possible,
    but errs on the side of caution/correctness when it needs to.

    Args:
      new_weights (np.ndarray): the new weights to use. Must have the
        same shape as the old ``np.ndarray``.
    """
    if new_weights is self._weights:
      return

    if not isinstance(new_weights, np.ndarray):
      raise TypeError('Expected an np.ndarray but got %s instead'
          % new_weights.__class__.__name__)

    if new_weights.shape != self._weights.shape:
      raise TypeError('Weight shape mismatch: %s != %s'
          % (new_weights.shape, self._weights.shape))

    self.ClearWeightBasedMemos()
    self._weights = new_weights

  def FeaturesAsNumPyArray(self, x):
    """A variant of ``Features`` which returns a ``np.ndarray``.

    For training we need to have the feature function return an
    ``np.ndarray(float)`` rather than the ``list(FeatureValue)`` used
    elsewhere. This function performes the necessary conversion.

    N.B., at present we do not memoize this function. The underlying
    ``Features`` method is memoized, so we won't re-compute the features
    each time; but we will repeatedly copy the floats into newly allocated
    ``np.ndarray`` objects. If that turns out to be a performance
    bottleneck, we can add the extra layer of memoization to avoid that.
    """
    fx = self.Features(x)
    return lambda y: np.array([fxy.value for fxy in fx(y)])

  def LogLikelihood(self):
    """The conditional log-likelihood of the training data.

    The conditional likelihood of the training data is the product
    of ``Pr(y|x)`` for each ``(x, y)`` pair in the training data; so
    the conditional log-likelihood is the log of that. This is called
    "likelihood" because it is thought of as a function of the weight
    covector, with the training data held fixed.

    This is the ideal objective function for training the weights, as it
    will give us the MLE weight covector for the training data. However,
    in practice, we want to do regularization to ensure we don't overfit
    the training data and to reduce classification time by ensuring that
    the weight vector is sparse. Thus, the actual objective function
    will be the log-likelihood plus some penalty terms for regularization.
    """
    observed_zeta = math.fsum(self.LogZ(x) for x, _ in self._training_data)
    observed_score = self.weights.dot(self._observed_feature_vector)
    return observed_score - observed_zeta

  def LogLikelihoodGradient(self):
    """The gradient (aka Jacobian) of ``LogLikelihood``."""
    expected_feature_vector = vsum([
        self.Expectation(x, self.FeaturesAsNumPyArray(x))
        for x, _ in self._training_data])
    return self._observed_feature_vector - expected_feature_vector

  def TrainWeights(self, l2_penalty):
    """Optimize the weight covector based on the training data.

    Args:
      l2_penalty (float): the hyperparameter for how much to penalize
        weight covectors far from zero.

    Returns:
      Nothing, but has the side effect of mutating the stored weights.
    """
    initial_weights = self.weights

    # We want to minimize the number of times we reset the weights since
    # that clears our memos. One might think we could do that in the
    # between-iterations callback; but actually, in a single iteration,
    # BFGS calls the objective function and gradient more than once with
    # different arguments; so, alas, we must reset the weights in both.
    # This is why the ``weights`` setter tries to avoid clearing memos
    # when possible.

    def objective_function(new_weights):
      self.weights = new_weights
      return -self.LogLikelihood() + 0.5 * l2_penalty * self.quadrance

    def objective_function_gradient(new_weights):
      self.weights = new_weights
      return -self.LogLikelihoodGradient() + l2_penalty * self.weights

    result = spo.minimize(
        objective_function,
        initial_weights,
        method='BFGS',
        jac=objective_function_gradient)

    if not result.success: # pragma: no cover
      # This should happen infrequently enough that there's no point in
      # logging it and attempting to carry on.
      raise Exception(
          'TrainableLogLinearModel.TrainWeights failed:'
          '\n\tReason: %s'
          '\n\tCurrent objective value: %s'
          '\n\tCurrent objective gradient: %s'
          '\n\tIterations: %d'
          '\n\tFunction evaluations: %d'
          '\n\tGradient evaluations: %d'
          % (result.message, result.fun, result.jac, result.nit, result.nfev,
             result.njev))

    # This shouldn't really be necessary, since we're resetting it
    # directly during training; but just to be safe/sure.
    self.weights = result.x
