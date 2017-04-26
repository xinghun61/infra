# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math

from crash.loglinear.feature import MetaFeatureValue
from libs.meta_object import MetaDict


class Weight(float):
  """Float-like class that represents the weight for a feature."""

  def __len__(self):
    return 1

  @property
  def l0(self):
    """The l0-norm of the weight.

    N.B., despite being popularly called the "l0-norm", this isn't
    actually a norm in the mathematical sense."""
    return bool(self)

  @property
  def l1(self):
    """The l1 (aka: Manhattan) norm of the weight."""
    return math.fabs(self)

  @property
  def quadrance(self):
    """The square of the l2 norm of the weight.

    This value is often more helpful to have direct access to, as it
    avoids the need for non-rational functions (e.g., sqrt) and shows up
    as its own quantity in many places. Also, computing it directly avoids
    the error introduced by squaring the square-root of an IEEE-754 float.
    """
    return math.fabs(self)**2

  def IsZero(self, epsilon):
    return math.fabs(self) <= epsilon


class MetaWeight(MetaDict):
  """Dict-like class mapping features in ``Metafeature`` to their weights."""

  def IsZero(self, epsilon):
    if not self:
      return True

    return all(weight.IsZero(epsilon) for weight in self.itervalues())

  def DropZeroWeights(self, epsilon=0.):
    """Drops all zero weights."""
    # Make all sub meta weights drop their zero weights.
    zero_keys = set()
    for key, weight in self.iteritems():
      if hasattr(weight, 'is_meta'):
        weight.DropZeroWeights(epsilon=epsilon)

      if weight.IsZero(epsilon):
        zero_keys.add(key)

    for key in zero_keys:
      del self[key]

  def __mul__(self, meta_feature):
    """``MetaWeight`` can multiply with ``MetaFeatureValue``."""
    # MetaWeight is a dense representation of a sparse array. So MetaWeight and
    # MetaFeature don't necessarily have the same length.
    return math.fsum(meta_feature[name] * weight
                     for name, weight in self.iteritems())

  __rmul__ = __mul__

  @property
  def l0(self):
    """The l0-norm of the meta weight.

    N.B., despite being popularly called the "l0-norm", this isn't
    actually a norm in the mathematical sense."""
    return math.fsum(weight.l0 for weight in self.itervalues())

  @property
  def l1(self):
    """The l1 (aka: Manhattan) norm of the meta weight."""
    return math.fsum(weight.l1 for weight in self.itervalues())

  @property
  def quadrance(self):
    """The square of the l2 norm of the meta weight.

    This value is often more helpful to have direct access to, as it
    avoids the need for non-rational functions (e.g., sqrt) and shows up
    as its own quantity in many places. Also, computing it directly avoids
    the error introduced by squaring the square-root of an IEEE-754 float.
    """
    return math.fsum(weight.quadrance for weight in self.itervalues())
