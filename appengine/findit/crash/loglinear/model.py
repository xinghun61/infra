# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(http://crbug.com/669639): there are lots of ways to make the code
# in this file better. We avoid having separate todos per task; instead
# see that meta-issue ticket.

import math
import numpy as np
# N.B., ``np.array`` can't take generators; you must pass explicit lists.

from libs.math.functions import MemoizedFunction
from libs.math.logarithms import logsumexp
from libs.math.vectors import vsum

EPSILON = 0.00001


def ToFeatureFunction(fs):
  """Given an array of scalar-valued functions, return an array-valued function.

  Args:
    fs (iterable): A collection of curried functions ``X -> Y -> A``.
      That is, given a particular ``x`` they return a function ``Y -> A``.

  Returns:
    A function ``X -> Y -> list(A)`` where for all ``x``, ``y``, and
    ``i`` we have that ``ToFeatureFunction(fs)(x)(y)[i] == fs[i](x)(y)``.
  """
  def _FeatureFunction(x):
    fxs = [f(x) for f in fs]
    return lambda y: [fx(y) for fx in fxs]

  return _FeatureFunction


class UnnormalizedLogLinearModel(object):
  """An unnormalized loglinear model.

  We use this model for combining a bunch of different features in order
  to decide who to blame. In particular, the nice thing about loglinear
  models is that (a) they allow separating the amount of weight we
  give to each feature from the feature itself, and (b) they allow us
  to keep adding features at will without needing to worry about the
  fiddly details needed for it to be a probability model.

  Throughout the documentation we use the following conventional
  terminology. The independent variable (aka: the given data which
  sets up the classification problem) is called ``X``, where particular
  values for that variable called ``x``. The dependent variable (aka:
  the answers/labels returned by classification) is called ``Y``,
  where particular values for that random variable called ``y``. The
  partition function is called ``Z``. And, somewhat non-conventionally,
  we will call the log of the partition function ``zeta``.

  This class is distinct from ``LogLinearModel`` in that we do not require
  a specification of ``Y``. This class is sufficient for determining
  which ``y`` is the most likely, though it can only return a "score"
  rather than returning a probability per se.
  """

  def __init__(self, feature_function, weights, epsilon=None):
    """Construct a new model with the given weights and feature function.

    Args:
      feature_function: A function ``X -> Y -> list(FeatureValue)``. N.B.,
        for all ``x`` and ``y`` the length of ``feature_function(x)(y)``
        must be the same as the length of ``weights``.
      weights (list of float): coefficients for how important we consider
        each component of the feature vector for deciding which ``y``
        to blame.
      epsilon (float): The absolute-error threshold for considering a
        weight to be "equal to zero". N.B., this should be a positive
        number, as we will compare it against the absolute value of
        each weight.
    """
    if epsilon is None:
      epsilon = EPSILON
    self._weights = np.array([
        w if isinstance(w, float) and math.fabs(w) >= epsilon else 0.
        for w in weights])

    self._quadrance = None

    # TODO(crbug.com/674752): we need better names for ``self._features``.
    def _FeaturesMemoizedOnY(x):
      fx = feature_function(x)
      def _TypeCheckFeatures(y):
        fxy = fx(y)
        # N.B., we're assuming that ``len(self.weights)`` is O(1).
        assert len(fxy) == len(self.weights), TypeError(
            "vector length mismatch: %d != %d" % (len(fxy), len(self.weights)))
        return fxy
      return MemoizedFunction(_TypeCheckFeatures)
    self._features = MemoizedFunction(_FeaturesMemoizedOnY)

    # TODO(crbug.com/674752): we need better names for ``self._scores``.
    # N.B., this is just the inner product of ``self.weights``
    # against ``self._features(x)``. If we can compute this in some
    # more efficient way, we should. In particular, we will want to
    # make the weights sparse, in which case we need to use a sparse
    # variant of the dot product.
    self._scores = MemoizedFunction(lambda x:
        self._features(x).map(lambda fxy:
            self.weights.dot(np.array(map(lambda feature:
                feature.value, fxy)))))

  def ClearWeightBasedMemos(self):
    """Clear all the memos that depend on the weight covector."""
    self._quadrance = None
    self._scores.ClearMemos()

  def ClearAllMemos(self):
    """Clear all memos, even those independent of the weight covector."""
    self.ClearWeightBasedMemos()
    self._features.ClearMemos()

  @property
  def weights(self):
    """The weight covector.

    At present we return the weights as an ``np.ndarray``, but in the
    future that may be replaced by a more general type which specifies
    the semantics rather than the implementation details.
    """
    return self._weights

  @property
  def l0(self): # pragma: no cover
    """The l0-norm of the weight covector.

    N.B., despite being popularly called the "l0-norm", this isn't
    actually a norm in the mathematical sense."""
    return float(np.count_nonzero(self.weights))

  @property
  def l1(self): # pragma: no cover
    """The l1 (aka: Manhattan) norm of the weight covector."""
    return math.fsum(math.fabs(w) for w in self.weights)

  @property
  def quadrance(self):
    """The square of the l2 norm of the weight covector.

    This value is often more helpful to have direct access to, as it
    avoids the need for non-rational functions (e.g., sqrt) and shows up
    as its own quantity in many places. Also, computing it directly avoids
    the error introduced by squaring the square-root of an IEEE-754 float.
    """
    if self._quadrance is None:
      self._quadrance = math.fsum(math.fabs(w)**2 for w in self.weights)

    return self._quadrance

  @property
  def l2(self):
    """The l2 (aka Euclidean) norm of the weight covector.

    If you need the square of the l2-norm, do not use this property.
    Instead, use the ``quadrance`` property which is more accurate than
    squaring this one.
    """
    return math.sqrt(self.quadrance)

  def Features(self, x):
    """Returns a function mapping ``y`` to its feature vector given ``x``.

    Args:
      x (X): the value of the independent variable.

    Returns:
      A ``MemoizedFunction`` of type ``Y -> np.array(float)``.
    """
    return self._features(x)

  def Score(self, x):
    """Returns a function mapping ``y`` to its "score" given ``x``.

    Semantically, the "score" of ``y`` given ``x`` is the
    unnormalized log-domain conditional probability of ``y`` given
    ``x``. Operationally, we compute this by taking the inner product
    of the weight covector with the ``Features(x)(y)`` vector. The
    conditional probability itself can be computed by exponentiating
    the "score" and normalizing with the partition function. However,
    for determining the "best" ``y`` we don't need to bother computing
    the probability, because ``Score(x)`` is monotonic with respect to
    ``Probability(x)``.

    Args:
      x (X): the value of the independent variable.

    Returns:
      A ``MemoizedFunction`` of type ``Y -> float``.
    """
    return self._scores(x)


class LogLinearModel(UnnormalizedLogLinearModel):
  """A loglinear probability model.

  This class is distinct from ``UnnormalizedLogLinearModel`` in that
  we can provide probabilities (not just scores). However, to do so we
  require a specification of the entire set ``Y``.
  """
  def __init__(self, Y, feature_function, weights, epsilon=None):
    """Construct a new probabilistic model.

    Args:
      Y (iterable): the entire range of values for the independent
        variable. This is needed for computing the partition function.
      feature_function: A function ``X -> Y -> list(float)``. N.B.,
        for all ``x`` and ``y`` the length of ``feature_function(x)(y)``
        must be the same as the length of ``weights``.
      weights (list of float): coefficients for how important we consider
        each component of the feature vector for deciding which ``y``
        to blame.
      epsilon (float): The absolute-error threshold for considering a
        weight to be "equal to zero". N.B., this should be a positive
        number, as we will compare it against the absolute value of
        each weight.
    """
    super(LogLinearModel, self).__init__(feature_function, weights, epsilon)

    self._Y = frozenset(Y)

    def _LogZ(x):
      score_given_x = self._scores(x)
      return logsumexp([score_given_x(y) for y in self._Y])
    self._zetas = MemoizedFunction(_LogZ)

  def ClearWeightBasedMemos(self):
    """Clear all the memos that depend on the weight covector."""
    super(LogLinearModel, self).ClearWeightBasedMemos()
    self._zetas.ClearMemos()

  def Z(self, x):
    """The normal-domain conditional partition-function given ``x``.

    If you need the log of the partition function, do not use this
    method. Instead, use the ``LogZ`` method which computes it directly
    and thus is more accurate than taking the log of this one.

    Args:
      x (X): the value of the independent variable.

    Returns:
      The normalizing constant of ``Probability(x)``.
    """
    return math.exp(self.LogZ(x))

  def LogZ(self, x):
    """The log-domain conditional partition-function given ``x``.

    Args:
      x (X): the value of the independent variable.

    Returns:
      The normalizing constant of ``LogProbability(x)``.
    """
    return self._zetas(x)

  def Probability(self, x):
    """The normal-domain distribution over ``y`` given ``x``.

    That is, ``self.Probability(x)(y)`` returns ``p(y | x; self.weights)``
    which is the model's estimation of ``Pr(y|x)``.

    If you need the log-probability, don't use this method. Instead,
    use the ``LogProbability`` method which computes it directly and
    thus is more accurate than taking the log of this one.
    """
    logprob_given_x = self.LogProbability(x)
    return lambda y: math.exp(logprob_given_x(y))

  def LogProbability(self, x):
    """The log-domain distribution over ``y`` given ``x``.

    That is, ``self.LogProbability(x)(y)`` returns the log of
    ``self.Probability(x)(y)``. However, this method computes the
    log-probabilities directly and so is more accurate and efficient
    than taking the log of ``Probability``.
    """
    zeta_x = self.LogZ(x)
    score_given_x = self.Score(x)
    return lambda y: score_given_x(y) - zeta_x

  def Expectation(self, x, f):
    """Compute the expectation of a function with respect to ``Probability(x)``.

    Args:
      x (X): the value of the independent variable.
      f: a function of type ``Y -> np.ndarray(float)``.

    Returns:
      An ``np.ndarray`` of ``float`` called the "expected value". N.B.,
      the particular array returned may not actually be one that the
      function returns; rather, it's a sort of average of all the results
      returned. For more information you can take a look at Wikipedia
      <https://en.wikipedia.org/wiki/Expected_value>.
    """
    prob_given_x = self.Probability(x)
    # N.B., the ``*`` below is vector scaling! If we want to make this
    # method polymorphic in the return type of ``f`` then we'll need an
    # API that provides both scaling and ``vsum``.
    return vsum([prob_given_x(y) * f(y) for y in self._Y])

