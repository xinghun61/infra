# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import OrderedDict
import math
import numpy as np
# N.B., ``np.array`` can't take generators; you must pass explicit lists.
import scipy.optimize as spo

from analysis.linear.model import LogLinearModel
from analysis.linear.weight import MetaWeight
from analysis.linear.weight import Weight
from common.exceptions import PredatorError
from libs.meta_dict_serializer import GetSerializer
from libs.math.vectors import vsum
# N.B., ``vsum`` can't take generators; you must pass explicit lists.


class TrainableLogLinearModel(LogLinearModel):
  """A loglinear model with labelled data set for training the meta_weight."""

  def __init__(self, Y_given_X, training_data, meta_feature, meta_weight,
               epsilon=None):
    """
    Args:
      Y_given_X: a function from ``X`` to an iterable object giving the
        subset of ``Y`` which has non-zero probability given the
        ``x``. When in doubt about whether some ``y`` has zero probability
        or not, it is always safe/correct to return a larger subset of
        ``Y`` (it'll just take more computation time is all). This is
        needed for computing the partition function and expectation. N.B.,
        we do not actually need to know/enumerate of *all* of ``Y``,
        only the subsets for each ``x``.
      training_data (iterable): a collection of ``(x, y)`` pairs where
        ``y`` is the known-correct label for ``x``.
      meta_feature: A function from ``X`` to ``Y`` to a list of
        ``float``. N.B., the length of the list must be the same for all
        ``x`` and ``y``, and must be the same as the length of the list
        of meta_weight.
      meta_weight (dict from str to (Vector)Weight): the pre-training
        coefficients for how much we believe components of the feature vector.
        This provides the seed for training; this starting value shouldn't
        affect the final meta_weight obtained by training (thanks to
        convexity), but will affect how long it takes for training
        to converge.
        N.B. The dict should not be sparse (only contains non-zero meta_weight),
        because we only train those features whose names are keys in this dict.
      epsilon (float): The absolute-error threshold for considering a
        weight to be "equal to zero". N.B., this should be a positive
        number, as we will compare it against the absolute value of
        each weight.
    """
    super(TrainableLogLinearModel, self).__init__(
        Y_given_X, meta_feature, meta_weight, epsilon)
    self._training_data = training_data
    # Use self._meta_weight instead of initialz_meta_weight,
    # since self._meta_weight already filtered zero meta_weight in the __init__
    # of superclass.
    self._serializer = GetSerializer(meta_feature)
    self._np_weight = self._MetaToNumPyArray(self.meta_weight)
    self._observed_feature_vector = vsum([
        self.FeaturesAsNumPyArray(x)(y)
        for x, y in self._training_data])

  @property
  def np_weight(self):
    """The NumPy Array of the weight covector."""
    return self._np_weight

  @np_weight.setter
  def np_weight(self, new_np_weight): # pylint: disable=W0221
    """Mutate the weight covector, and clear memos as necessary.

    This setter attempts to avoid clearing memos whenever possible,
    but errs on the side of caution/correctness when it needs to.
    This setter also drop all the zero meta_weight in weight covector using
    self._epsilon.

    Note, the conversion between dict and np array is needed because model uses
    dict to organize meta_weight of features, however SciPy trainning
    (e.g. BFGS) needs numpy array to do computaion.

    Args:
      new_np_weight (np.ndarray): the new meta_weight to use. It will be
      converted to meta_weight dict mapping feature_name to its weight.
    """
    if np.array_equal(self._np_weight, new_np_weight):
      return

    if not isinstance(new_np_weight, np.ndarray):
      raise TypeError('Expected an np.ndarray but got %s instead' %
                      new_np_weight.__class__.__name__)

    if new_np_weight.shape != self._np_weight.shape:
      raise TypeError('Weight shape mismatch: %s != %s' %
                      (new_np_weight.shape, self._np_weight.shape))

    self._np_weight = new_np_weight
    self.meta_weight = self._NumPyArrayToMeta(self.np_weight)
    self.ClearWeightBasedMemos()

  def _NumPyArrayToMeta(self, np_weight):
    """Converts numpy array to dict (mapping feature name to weight).

    Note, this conversion is needed because model uses meta_weight dict to
    organize meta_weight for features, however SciPy trainning (e.g. BFGS) needs
    numpy array to do computaion.

    Args:
      np_weight (np.ndarray): meta_weight which have the same order of
        self._ordered_feature_to_len. Note, featuer np array should also be
        serialized by the same order as self._ordered_feature_to_len to match.

    Returns:
      A dict mapping feature name to weight.
    """
    return self._serializer.FromList(np_weight, meta_constructor=MetaWeight,
                                     element_constructor=Weight)

  def _MetaToNumPyArray(self, meta_weight):
    """Converts dict (mapping feature name to weight) to numpy array."""
    return np.array(self._serializer.ToList(meta_weight, default=Weight(0)))

  def FeaturesAsNumPyArray(self, x):
    """A variant of ``Features`` which returns a ``np.ndarray``.

    Note, the features nparray should have the same order as in
    self._ordered_feature_to_len to stay aligned with meta_weight np array.

    For training we need to have the feature function return an
    ``np.ndarray(float)`` rather than the ``list(FeatureValue)`` used
    elsewhere. This function performes the necessary conversion.

    N.B., at present we do not memoize this function. The underlying
    ``Features`` method is memoized, so we won't re-compute the features
    each time; but we will repeatedly copy the floats into newly allocated
    ``np.ndarray`` objects. If that turns out to be a performance
    bottleneck, we can add the extra layer of memoization to avoid that.
    """
    return lambda y: np.array(self._serializer.ToList(self.Features(x)(y)))

  def LogLikelihood(self):
    """The conditional log-likelihood of the training data.

    The conditional likelihood of the training data is the product
    of ``Pr(y|x)`` for each ``(x, y)`` pair in the training data; so
    the conditional log-likelihood is the log of that. This is called
    "likelihood" because it is thought of as a function of the weight
    covector, with the training data held fixed.

    This is the ideal objective function for training the meta_weight, as it
    will give us the MLE weight covector for the training data. However,
    in practice, we want to do regularization to ensure we don't overfit
    the training data and to reduce classification time by ensuring that
    the weight vector is sparse. Thus, the actual objective function
    will be the log-likelihood plus some penalty terms for regularization.
    """
    observed_zeta = math.fsum(self.LogZ(x) for x, _ in self._training_data)
    observed_score = self.np_weight.dot(
        self._observed_feature_vector)
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
      Nothing, but has the side effect of mutating the stored meta_weight.
    """
    initial_np_weight = self.np_weight

    # We want to minimize the number of times we reset the meta_weight since
    # that clears our memos. One might think we could do that in the
    # between-iterations callback; but actually, in a single iteration,
    # BFGS calls the objective function and gradient more than once with
    # different arguments; so, alas, we must reset the meta_weight in both.
    # This is why the ``meta_weight`` setter tries to avoid clearing memos
    # when possible.

    def objective_function(new_np_weight):
      self.np_weight = new_np_weight
      return -self.LogLikelihood() + 0.5 * l2_penalty * self.quadrance

    def objective_function_gradient(new_np_weight):
      self.np_weight = new_np_weight
      return -self.LogLikelihoodGradient() + l2_penalty * self.np_weight

    result = spo.minimize(
        objective_function,
        initial_np_weight,
        method='BFGS',
        jac=objective_function_gradient)

    if not result.success: # pragma: no cover
      # This should happen infrequently enough that there's no point in
      # logging it and attempting to carry on.
      raise PredatorError(
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
    self.np_weight = result.x
