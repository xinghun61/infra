# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import math

import libs.math.logarithms as lmath


def LinearlyScaled(value, maximum):
  """Returns a value scaled linearly between 0 and 1.

  Args:
    value (float): the value to be scaled.
    maximum (float): the maximum value to consider. Must be strictly
      positive and finite (i.e., can't be zero nor infinity).

  Returns:
    A ``float`` between 0 and 1. When the value is 0 we return 1. When
    the value is greater than the maximum, we return 0. With intermediate
    values scaled linearly.
  """
  return (maximum - min(maximum, value)) / maximum


def LogLinearlyScaled(value, maximum):
  """Returns a value scaled between -inf and 0.

  That is, we return the log of ``LinearlyScaled(value, maximum)``. Note
  that because of the behavior of logarithms, if this function is used to
  give the value of a feature then the weight of that feature specifies
  the order of the polynomial of the linearly-scaled value. That is,
  we have the equivalences:

  ``w * LogLinearlyScaled(value, maximum)
  == w * log(LinearlyScaled(value, maximum))
  == log(LinearlyScaled(value, maximum) ** w)``

  Thus, there is no point in defining a so-called "LogQuadraticallyScaled"
  function, or similar.

  Args:
    value (float): the value to be scaled.
    maximum (float): the maximum value to consider. Must be strictly
      positive and finite (i.e., can't be zero nor infinity).

  Returns:
    A ``float`` between -inf and 0. When the value is 0 we return
    0. When the value is greater than the maximum, we return -inf. With
    intermediate values scaled exponentially.
  """
  if math.isinf(maximum) or value >= maximum:
    return lmath.LOG_ZERO

  return lmath.log((maximum - min(maximum, value)) / maximum)


class ChangedFile(namedtuple('ChangedFile',
    ['name', 'blame_url', 'reasons'])): # pragma: no cover
  """Information about a file which changed causing a feature to blame it.

  Attributes:
    name (str): the file that changed
    blame_url (str or None): the ``StackFrame.BlameUrl`` of the given frame.
    reasons (list of str): A list of reasons this file change was blamed.
  """
  __slots__ = ()

  def ToDict(self):
    return {
        'file': self.name,
        'blame_url': self.blame_url,
        'info': '\n'.join(self.reasons)
      }

  def __str__(self):
    return ('%s(name = %s, blame_url = %s, reasons = %s)'
        % (self.__class__.__name__, self.name, self.blame_url, self.reasons))


class FeatureValue(namedtuple('FeatureValue',
    ['name', 'value', 'reason', 'changed_files'])): # pragma: no cover
  """The result of an individual feature.

  Attributes:
    name (str): the name of the feature producing this value.
    value (convertable to float): the value itself. N.B. we call the
      ``float`` builtin function to coerce this value to float; thus
      it is okay to pass an ``int`` or ``bool`` value as well.
    reason (str): some explanation of where the value came from.
    changed_files (list of ChangedFile, or None): A list of files changed
      by the ``Suspect`` annotated with reasons why the feature function
      generating this object blames those changes.
  """
  __slots__ = ()

  def __new__(cls, name, value, reason, changed_files):
    return super(cls, FeatureValue).__new__(cls,
        str(name), float(value), str(reason), changed_files)

  def __str__(self):
    return ('%s(name = %s, value = %f, reason = %s, changed_files = %s)'
        % (self.__class__.__name__, self.name, self.value, self.reason,
           self.changed_files))


class Feature(object):
  """Abstract base class for features use by loglinear models."""

  @property
  def name(self):
    """The name of this feature."""
    raise NotImplementedError()

  def __call__(self, report):
    """Returns a value for a ``y`` given some ``x``.

    The loglinear model this feature is used in will specify some types
    ``X`` and ``Y``, as described in the documentation there. As an
    example: for the CL classifier, ``X`` is ``CrashReport`` and ``Y`` is
    ``Suspect``. Given those two types, this method is a curried function
    of type ``X -> Y -> FeatureValue``. That is, given some ``x`` of type
    ``X``, we return a function of type ``Y -> FeatureValue``, where
    the final result for each ``y`` of type ``Y`` is the value of that
    ``y`` given that ``x``.

    Values closer to zero indicate this feature has less to say about
    whether the ``y`` is to be blamed. Values further from zero indicate
    that this feature has more to say about it. (Whether this feature
    thinks the ``y`` should be blamed or should not be depends on the sign
    of the value and the sign of the weight given to this feature.) As
    special cases, a value of negative infinity means "do not blame this
    ``y`` no matter what any other features say", and a value of positive
    infinity means "definitely blame this ``y`` no matter what any other
    features say". Both of those special values should be used sparingly,
    since they override the model's ability to combine multiple sources of
    information and decide the cuplrit based on all the evidence together.
    """
    raise NotImplementedError()
