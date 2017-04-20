# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(http://crbug.com/669639): there are lots of ways to make the code
# in this file better. We avoid having separate todos per task; instead
# see that meta-issue ticket.

import logging
import math
import numpy as np
# N.B., ``np.array`` can't take generators; you must pass explicit lists.

from libs.math.functions import MemoizedFunction
from libs.math.logarithms import logsumexp
from libs.math.vectors import vsum

EPSILON = 0.00001
_FEATURE_TO_REASON_PRIORITY = {'MinDistance': 0,
                               'TopFrameIndex': -1,
                               'TouchCrashedDirectory': -2,
                               'TouchCrashedFile': -3}


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
  partition function is called ``Z``. And (somewhat non-conventionally)
  we will call the log of the partition function ``zeta``.

  This class is distinct from ``LogLinearModel`` in that we do not require
  a specification of ``Y``. This class is sufficient for determining
  which ``y`` is the most likely, though it can only return a "score"
  rather than returning a probability per se.
  """

  def __init__(self, meta_feature, meta_weight, epsilon=None):
    """Construct a new model with the meta_feature and meta_weight.

    Args:
      meta_feature (MetaFeature): A function ``X -> Y -> MetaFeatureValue``.
        N.B., for all ``x`` and ``y`` the length of ``wrapped_feature(x)(y)``
        must be the same as the length of ``weights``.
       All features.
      meta_weight (MetaWeight): All weights. the weights for the features.
        The keys of the dictionary are the names of the feature that weight is
        for. We take this argument as a dict rather than as a list so that
        callers needn't worry about what order to provide the weights in.
      epsilon (float): The absolute-error threshold for considering a
        weight to be "equal to zero". N.B., this should be a positive
        number, as we will compare it against the absolute value of
        each weight.
    """
    self._epsilon = EPSILON if epsilon is None else epsilon

    self._meta_weight = meta_weight
    self._meta_weight.DropZeroWeights(self._epsilon)

    self._quadrance = None
    # TODO(crbug.com/674752): we need better names for ``self._features``.
    def _Features(x):
      """Wrap ``meta_feature`` to memoize things.

      This outer wrapping takes each ``x`` to a memoized instance of
      ``_FeaturesGivenX``. That is, for each ``x`` we return a
      ``MemoizedFunction`` from ``Y`` to ``dict(str to FeatureValue)``.
      """
      # Memoize on ``Y``, to ensure we don't need to recompute
      # ``FeatureValue``s nor recheck the lengths.
      return MemoizedFunction(meta_feature(x))

    # Memoize on ``X``, to ensure we share the memo tables on ``Y``.
    self._features = MemoizedFunction(_Features)

    # TODO(crbug.com/674752): we need better names for ``self._scores``.
    # N.B., this is just the inner product of ``self._meta_weight``
    # against ``self._features(x)``. If we can compute this in some
    # more efficient way, we should. In particular, we will want to
    # make the weights sparse, in which case we need to use a sparse
    # variant of the dot product.
    self._scores = MemoizedFunction(lambda x: self._features(x).map(
        lambda fxy: self._meta_weight * fxy))

  def ClearWeightBasedMemos(self):
    """Clear all the memos that depend on the weight covector."""
    self._quadrance = None
    self._scores.ClearMemos()

  def ClearAllMemos(self):
    """Clear all memos, even those independent of the weight covector."""
    self.ClearWeightBasedMemos()
    self._features.ClearMemos()

  @property
  def meta_weight(self):
    """The weight covector.

    At present we return the weights as an dict mapping feature name to its
    weight, but in the future that may be replaced by a more general type which
    specifies the semantics rather than the implementation details.
    """
    return self._meta_weight

  @meta_weight.setter
  def meta_weight(self, new_meta_weight):
    self._meta_weight = new_meta_weight
    self._meta_weight.DropZeroWeights(self._epsilon)

  @property
  def l0(self): # pragma: no cover
    """The l0-norm of the weight covector.

    N.B., despite being popularly called the "l0-norm", this isn't
    actually a norm in the mathematical sense."""
    return self._meta_weight.l0

  @property
  def l1(self): # pragma: no cover
    """The l1 (aka: Manhattan) norm of the weight covector."""
    return self._meta_weight.l1

  @property
  def quadrance(self):
    """The square of the l2 norm of the weight covector.

    This value is often more helpful to have direct access to, as it
    avoids the need for non-rational functions (e.g., sqrt) and shows up
    as its own quantity in many places. Also, computing it directly avoids
    the error introduced by squaring the square-root of an IEEE-754 float.
    """
    return self._meta_weight.quadrance

  @property
  def l2(self):
    """The l2 (aka Euclidean) norm of the weight covector.

    If you need the square of the l2-norm, do not use this property.
    Instead, use the ``quadrance`` property which is more accurate than
    squaring this one.
    """
    return math.sqrt(self.quadrance)

  # TODO(crbug.com/673964): something better for detecting "close to log(0)".
  def LogZeroish(self, x):
    """Determine whether a float is close enough to log(0).

    If a ``FeatureValue`` has a (log-domain) score of -inf for a given
    ``Suspect``, then that suspect has zero probability of being the
    culprit. We want to filter these suspects out, to clean up the
    output of classification; so this method encapsulates the logic of
    that check.

    Args:
      x (float): the float to check

    Returns:
      ``True`` if ``x`` is close enough to log(0); else ``False``.
    """
    return x < 0 and math.isinf(x)

  def Features(self, x):
    """Returns a function mapping ``y`` to its feature vector given ``x``.

    Args:
      x (X): the value of the independent variable.

    Returns:
      A ``MemoizedFunction`` of type ``Y -> dict(str to float)``.
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

  def FilterReasonWithWeight(self, reason):
    """Filters reasons with zero weights.

    Args:
      reason (dict): Dict mapping feature name to reason string.

    Returns:
      A list of reason strings.
    """
    flat_weight = self._meta_weight.flat_dict

    filtered_reasons = {}
    for non_zero_feature in flat_weight:
      if non_zero_feature in reason:
        filtered_reasons[non_zero_feature] = reason[non_zero_feature]

    sorted_reasons = sorted(
        filtered_reasons.items(),
        key=lambda item: _FEATURE_TO_REASON_PRIORITY.get(
            item[0], -float('inf')))

    return [reason for _, reason in sorted_reasons]


class LogLinearModel(UnnormalizedLogLinearModel):
  """A loglinear probability model.

  This class is distinct from ``UnnormalizedLogLinearModel`` in that
  we can provide probabilities (not just scores). However, to do so we
  require a specification of the subsets of ``Y`` for each ``x``.
  """
  def __init__(self, Y_given_X, meta_feature, meta_weight, epsilon=None):
    """Construct a new probabilistic model.

    Args:
      Y_given_X: a function from ``X`` to an iterable object giving the
        subset of ``Y`` which has non-zero probability given the
        ``x``. When in doubt about whether some ``y`` has zero probability
        or not, it is always safe/correct to return a larger subset of
        ``Y`` (it'll just take more computation time is all). This is
        needed for computing the partition function and expectation. N.B.,
        we do not actually need to know/enumerate of *all* of ``Y``,
        only the subsets for each ``x``.
      meta_feature (MetaFeature): A function ``X -> Y -> MetaFeatureValue``.
        N.B., for all ``x`` and ``y`` the length of ``wrapped_feature(x)(y)``
        must be the same as the length of ``weights``.
       All features.
      meta_weight (MetaWeight): All weights. the weights for the features.
        The keys of the dictionary are the names of the feature that weight is
        for. We take this argument as a dict rather than as a list so that
        callers needn't worry about what order to provide the weights in.
      epsilon (float): The absolute-error threshold for considering a
        weight to be "equal to zero". N.B., this should be a positive
        number, as we will compare it against the absolute value of
        each weight.
    """
    super(LogLinearModel, self).__init__(meta_feature, meta_weight, epsilon)

    self._Y = Y_given_X

    def _LogZ(x):
      score_given_x = self._scores(x)
      return logsumexp([score_given_x(y) for y in self._Y(x)])
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

    That is, ``self.Probability(x)(y)`` returns ``p(y | x; self._meta_weight)``
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
    return vsum([prob_given_x(y) * f(y) for y in self._Y(x)])
