# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import logging
import math

import libs.math.logarithms as lmath
from libs.math.vectors import vsum
from libs.meta_object import Element
from libs.meta_object import MetaDict


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


class FeatureValue(Element): # pragma: no cover
  """The result of an feature.

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

  def __init__(self, name, value, reason, changed_files):
    self._value = float(value)
    self._name = name
    self._reason = reason
    self._changed_files = changed_files

  @property
  def name(self):
    return self._name

  @property
  def value(self):
    return self._value

  @property
  def reason(self):
    return ('%s:\n%s\n' % (self._name, self._reason)
            if self._reason else None)

  @property
  def changed_files(self):
    return self._changed_files

  def __str__(self):
    return ('%s(name = %s, value = %f, reason = %s, changed_files = %s)'
        % (self.__class__.__name__, self.name, self.value, self.reason,
           self.changed_files))

  def __len__(self):
    return 1

  def __mul__(self, number):
    return self._value * float(number)

  __rmul__ = __mul__

  def __add__(self, number):
    return self._value + float(number)

  __radd__ = __add__

  def __float__(self):
    return self._value

  def __eq__(self, other):
    return (self.name == other.name and self._value == other._value and
            self.reason == other.reason and
            self.changed_files == other.changed_files)

  def __ne__(self, other):
    return not self.__eq__(other)


class MetaFeatureValue(MetaDict):
  """The result of a meta feature which groups a list of ``FeatureValue``s.

  N.B. ``MetaFeatureValue`` must have more than one ``FeatureValue``.

  Attributes:

  """
  def __init__(self, name, feature_values):
    """
    Args:
      feature_value (dict of FeatureValue/MetaFeatureValue):
        All the sub features that this ``MetaFeatureValue`` contains.
    """
    super(MetaFeatureValue, self).__init__(feature_values)
    self._name = name
    self._reason = None
    self._changed_files = None

  @property
  def name(self):
    return self._name

  @property
  def reason(self):
    """Collect and format a list of all ``FeatureValue.reason`` strings.

    Returns:
      A str of reasons, each line has a format
      "feature_name: feature_value -- reason" triples; where the first string is
      the feature name, the float is some numeric representation of how
      much influence this feature exerts on the ``Suspect`` being blamed,
      and the final string is the ``FeatureValue.reason``. The list is
      sorted by feature name, just to ensure that it comes out in some
      canonical order.

      At present, the float is the log-domain score of the feature
      value. However, this isn't the best thing for UX reasons. In the
      future it might be replaced by the normal-domain score, or by
      the probability.
    """
    if self._reason:
      return self._reason

    formatted_reasons = []
    for feature in self.itervalues():
      if feature.reason:
        formatted_reasons.append(feature.reason)

    formatted_reasons.sort()
    self._reason = '\n'.join(formatted_reasons)
    return self._reason

  @property
  def changed_files(self):
    """Merge multiple``FeatureValue.changed_files`` lists into one.

    Returns:
      A list of ``ChangedFile`` objects sorted by file name. The sorting
      is not essential, but is provided to ease testing by ensuring the
      output is in some canonical order.

    Raises:
      ``ValueError`` if any file name is given inconsistent ``blame_url``s.
    """
    if self._changed_files:
      return self._changed_files

    all_changed_files = {}
    for feature in self.itervalues():
      if not feature.changed_files:
        continue

      for changed_file in feature.changed_files or []:
        accumulated_changed_file = all_changed_files.get(changed_file.name)
        if accumulated_changed_file is None:
          all_changed_files[changed_file.name] = changed_file
          continue

        if (accumulated_changed_file.blame_url !=
            changed_file.blame_url): # pragma: no cover
          raise ValueError('Blame URLs do not match: %s != %s'
              % (accumulated_changed_file.blame_url, changed_file.blame_url))
        accumulated_changed_file.reasons.extend(changed_file.reasons or [])

    self._changed_files = all_changed_files.values()
    self._changed_files.sort(key=lambda changed_file: changed_file.name)
    return self._changed_files

  def __len__(self):
    return len(self._value)

  def __eq__(self, other):
    return (self.name == other.name and self._value == other._value and
            self.reason == other.reason and
            self.changed_files == other.changed_files)

  def __ne__(self, other):
    return not self.__eq__(other)


class Feature(Element):
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
    of type ``X -> Y -> FeatureValue``. That is, given some ``x`` of
    type ``X``, we return a function of type ``Y -> FeatureValue``, where
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


class MetaFeature(MetaDict):
  """Abstract base class for meta features use by loglinear models.

  MetaFeature is a dict of (Meta)Features.
  """

  @property
  def name(self):
    """The name of this feature."""
    raise NotImplementedError()

  def __call__(self, x):
    """Returns a value for a ``y`` given some ``x``.

    The loglinear model this feature is used in will specify some types
    ``X`` and ``Y``, as described in the documentation there. As an
    example: for the CL classifier, ``X`` is ``CrashReport`` and ``Y`` is
    ``Suspect``. Given those two types, this method is a curried function
    of type ``X -> Y -> FeatureValue``. That is, given some ``x`` of
    type ``X``, we return a function of type ``Y -> FeatureValue``, where
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


class WrapperMetaFeature(MetaFeature):
  """Given a dict of scalar-valued functions, return an dict-valued function.

  Note, the features that get wrapped should be independent to each other, which
  means their feature values can be computed independently.

  Either wrap single Feature or wrap features whose final results are computed
  independently.

  Properties:
    fs (Feature of iterable of (Meta)Features): A collection of curried
    functions ``X -> Y -> (Meta)FeatureValue``. That is, given a particular
    ``x`` they return a function ``Y -> dict(FeatureValue)``. N.B. each function
    should have a name property.
  """
  def __init__(self, fs):
    super(WrapperMetaFeature, self).__init__({f.name: f for f in fs or []})

  @property
  def name(self):
    return 'WrapperFeature'

  def __call__(self, x):
    """Fuction mapping ``X -> Y -> dict(FeatureValue.name to FeatureValue).

    Returns:
      A function ``X -> Y -> dict(FeatureValue.name to FeatureValue)`` where for
      all ``x``, ``y``, and for a feature f in fs, we have
      ``FeatureFunction(fs)(x)(y)[f.name] == f(x)(y)``.
    """
    fxs = {name: f(x) for name, f in self.iteritems()}
    return lambda y: MetaFeatureValue(
        self.name, {name: fx(y) for name, fx in fxs.iteritems()})
