# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.math.functions import Function
from libs.math.functions import MemoizedFunction

# Some arbitrary functions:
_F = lambda x: x + 1
_G = lambda x: x * x


class FunctionsTest(unittest.TestCase):

  def testFunctionCall(self):
    """``Function.__call__`` returns same value as the underlying callable."""
    self.assertEqual(_F(5), Function(_F)(5))
    self.assertEqual(_G(5), Function(_G)(5))

  def testFunctionMap(self):
    """``Function.map`` composes functions as described in the docstring."""
    self.assertEqual(_G(_F(5)), Function(_F).map(_G)(5))
    self.assertEqual(_F(_G(5)), Function(_G).map(_F)(5))

  def testMemoizedFunctionCall(self):
    """``MemoizedFunction.__call__`` returns same value as its callable."""
    self.assertEqual(_F(5), MemoizedFunction(_F)(5))
    self.assertEqual(_G(5), MemoizedFunction(_G)(5))

  def testMemoizedFunctionMap(self):
    """``MemoizedFunction.map`` composes functions as described."""
    self.assertEqual(_G(_F(5)), MemoizedFunction(_F).map(_G)(5))
    self.assertEqual(_F(_G(5)), MemoizedFunction(_G).map(_F)(5))

  def testMemoization(self):
    """``MemoizedFunction.__call__`` actually does memoize.

    That is, we call the underlying function once (to set the memo), then
    we discard the underlying function (to be sure the next ``__call__``
    is handled from the memos, and finally call the function to check.
    """
    f = MemoizedFunction(_F)
    f(5)
    del f._f
    self.assertEqual(_F(5), f(5))

  def testClearMemos(self):
    """``MemoizedFunction._ClearMemos`` does actually clear the memos.

    That is, we call the underlying function once (to set the memo),
    then swap put the underlying function with a different one (to be
    sure we know whether the next ``__call__`` goes to the memos or to
    the function), and finally clear the memos and check.
    """
    f = MemoizedFunction(_F)
    f(5)
    f._f = _G
    f.ClearMemos()
    self.assertEqual(_G(5), f(5))
