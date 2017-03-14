# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math

from crash.loglinear.feature import MetaFeatureValue
from libs.meta_object import Element
from libs.meta_object import MetaDict


class Weight(Element):
  """Float-like class that represents the weight for a feature."""

  def __init__(self, value):
    super(Weight, self).__init__()
    self._value = float(value)

  @property
  def value(self):
    return self._value

  def __mul__(self, number):
    return Weight(self._value * float(number))

  __rmul__ = __mul__

  def __len__(self):
    return 1

  def __float__(self):
    return self.value

  def __eq__(self, other):
    return self._value == other._value

  def __ne__(self, other):
    return not self.__eq__(other)

  @property
  def l0(self):
    """The l0-norm of the weight.

    N.B., despite being popularly called the "l0-norm", this isn't
    actually a norm in the mathematical sense."""
    return float(bool(self._value))

  @property
  def l1(self):
    """The l1 (aka: Manhattan) norm of the weight."""
    return math.fabs(self._value)

  @property
  def quadrance(self):
    """The square of the l2 norm of the weight.

    This value is often more helpful to have direct access to, as it
    avoids the need for non-rational functions (e.g., sqrt) and shows up
    as its own quantity in many places. Also, computing it directly avoids
    the error introduced by squaring the square-root of an IEEE-754 float.
    """
    return math.fabs(self._value)**2

  def IsZero(self, epsilon):
    return math.fabs(self._value) <= epsilon


class MetaWeight(MetaDict):
  """Dict-like class mapping features in ``Metafeature`` to their weights."""

  def IsZero(self, epsilon):
    if not self._value:
      return True

    return all(weight.IsZero(epsilon) for weight in self.itervalues())

  def DropZeroWeights(self, epsilon=0.):
    """Drops all zero weights."""
    # Make all sub meta weights drop their zero weights.
    for weight in self.itervalues():
      if not weight.is_element:
        weight.DropZeroWeights(epsilon=epsilon)

    self._value = {name: weight for name, weight in self.iteritems()
                   if not weight.IsZero(epsilon)}

  def __len__(self):
    return len(self._value)

  def __mul__(self, meta_feature):
    """``MetaWeight`` can multiply with ``MetaFeatureValue``."""
    # MetaWeight is a dense representation of a sparse array. So MetaWeight and
    # MetaFeature don't necessarily have the same length.
    return math.fsum(meta_feature[name] * weight
                     for name, weight in self.iteritems())

  __rmul__ = __mul__

  def __eq__(self, other):
    if len(self) != len(other):
      return False

    for key, value in self.iteritems():
      if value != other.get(key):
        return False

    return True

  def __ne__(self, other):
    return not self.__eq__(other)

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
