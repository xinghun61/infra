# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Function(object):
  """Base class for mathematical functions.

  The ``callable`` interface is sufficient for when you only ever need to
  invoke a function. But many times we want to have more information about
  the function, such as getting its domain or range or knowing whether
  it's sparse. In addition, we often want to adjust the computational
  representation of functions (e.g., adding memoization). So this class
  provides a base class for functions supporting all these sorts of
  operations in addition to being callable.
  """

  def __init__(self, f):
    self._f = f

  def __call__(self, x):
    return self._f(x)

  def map(self, g):
    """Returns a new function that applies ``g`` after ``self``.

    Args:
      g (callable): the function to post-compose.

    Returns:
      An object of the same type as ``self`` which computes ``lambda x:
      g(self(x))``. N.B., although mathematically we have the equivalence:
      ``SomeFunction(f).map(g) == SomeFunction(lambda x: g(f(x)))``;
      operationally the left- and right-hand sides may differ. For
      example, with the ``MemoizedFunction`` class, the left-hand side
      will memoize the intermediate ``f(x)`` values whereas the right-hand
      side will not.
    """
    return self.__class__(lambda x: g(self(x)))


class MemoizedFunction(Function):
  """A function which memoizes its value for all arguments."""

  def __init__(self, f):
    super(MemoizedFunction, self).__init__(f)
    self._memos = {}

  def ClearMemos(self):
    """Discard all memoized results of this function."""
    self._memos = {}

  def __call__(self, x):
    try:
      return self._memos[x]
    except KeyError:
      fx = self._f(x)
      self._memos[x] = fx
      return fx
