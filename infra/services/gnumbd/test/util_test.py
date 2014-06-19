# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import textwrap
import collections

from infra.services.gnumbd.support import util


class TestCalledProcessError(unittest.TestCase):
  def testBasic(self):
    cpe = util.CalledProcessError(100, ('cat', 'dog'), None, None)
    self.assertEqual(
        str(cpe), "Command ('cat', 'dog') returned non-zero exit status 100.\n")

  def testErr(self):
    cpe = util.CalledProcessError(
        100, ('cat', 'dog'), None,
        'Cat says the dog smells funny.\nCat is not amused.')

    self.assertEqual(str(cpe), textwrap.dedent('''\
    Command ('cat', 'dog') returned non-zero exit status 100:
    STDERR ========================================
      Cat says the dog smells funny.
      Cat is not amused.
    '''))

  def testOut(self):
    cpe = util.CalledProcessError(
        100, ('cat', 'dog'),
        'This totally worked! Squirrels are awesome!',
        '')

    self.assertEqual(str(cpe), textwrap.dedent('''\
    Command ('cat', 'dog') returned non-zero exit status 100:
    STDOUT ========================================
      This totally worked! Squirrels are awesome!
    '''))

  def testBoth(self):
    cpe = util.CalledProcessError(
        100, ('cat', 'dog'),
        'This totally worked! Squirrels are awesome!',
        'Cat says the dog smells funny.\nCat is not amused.')

    self.assertEqual(str(cpe), textwrap.dedent('''\
    Command ('cat', 'dog') returned non-zero exit status 100:
    STDOUT ========================================
      This totally worked! Squirrels are awesome!
    STDERR ========================================
      Cat says the dog smells funny.
      Cat is not amused.
    '''))


class TestCachedProperty(unittest.TestCase):
  def setUp(self):
    self.calls = calls = []
    class Foo(object):
      def __init__(self, success=True, override=None):
        self.success = success
        self.override = override

      @util.cached_property
      def happy(self):
        calls.append(1)
        if self.override is not None:
          self._happy = self.override  # pylint: disable=W0201
        if not self.success:
          raise Exception('nope')
        return 'days'
    self.Foo = Foo

  def testBasic(self):
    f = self.Foo()
    self.assertEqual(f.happy, 'days')
    self.assertEqual(f.happy, 'days')
    self.assertEqual(sum(self.calls), 1)

  def testBareReturnsSelf(self):
    self.assertIsInstance(self.Foo.happy, util.cached_property)

  def testOverride(self):
    f = self.Foo(override='cowabunga!')
    self.assertEqual(f.happy, 'cowabunga!')
    self.assertEqual(f.happy, 'cowabunga!')
    self.assertEqual(sum(self.calls), 1)

  def testNoCache(self):
    f = self.Foo(False)
    with self.assertRaises(Exception):
      f.happy  # pylint: disable=W0104
    f.success = True
    self.assertEqual(f.happy, 'days')
    self.assertEqual(sum(self.calls), 2)

  def testDel(self):
    f = self.Foo()
    self.assertEqual(f.happy, 'days')
    self.assertEqual(f.happy, 'days')
    del f.happy
    self.assertEqual(f.happy, 'days')
    del f.happy
    del f.happy
    self.assertEqual(f.happy, 'days')
    self.assertEqual(sum(self.calls), 3)


class TestFreeze(unittest.TestCase):
  def testDict(self):
    d = collections.OrderedDict()
    d['cat'] = 100
    d['dog'] = 0

    f = util.freeze(d)
    self.assertEqual(d, f)
    self.assertIsInstance(f, util.FrozenDict)
    self.assertEqual(
        hash(f),
        hash((0, ('cat', 100))) ^ hash((1, ('dog', 0)))
    )
    self.assertEqual(len(d), len(f))

    # Cover equality
    self.assertEqual(f, f)
    self.assertNotEqual(f, 'dog')
    self.assertNotEqual(f, {'bob': 'hat'})
    self.assertNotEqual(f, {'cat': 20, 'dog': 10})

  def testList(self):
    l = [1, 2, {'bob': 100}]
    f = util.freeze(l)
    self.assertSequenceEqual(l, f)
    self.assertIsInstance(f, tuple)

  def testSet(self):
    s = {1, 2, util.freeze({'bob': 100})}
    f = util.freeze(s)
    self.assertEqual(s, f)
    self.assertIsInstance(f, frozenset)


class TestThaw(unittest.TestCase):
  def testDict(self):
    d = collections.OrderedDict()
    d['cat'] = 100
    d['dog'] = 0
    f = util.freeze(d)
    t = util.thaw(f)
    self.assertEqual(d, f)
    self.assertEqual(t, f)
    self.assertEqual(d, t)
    self.assertIsInstance(t, collections.OrderedDict)

  def testList(self):
    l = [1, 2, {'bob': 100}]
    f = util.freeze(l)
    t = util.thaw(f)
    self.assertSequenceEqual(l, f)
    self.assertSequenceEqual(f, t)
    self.assertSequenceEqual(l, t)
    self.assertIsInstance(t, list)

  def testSet(self):
    s = {1, 2, 'cat'}
    f = util.freeze(s)
    t = util.thaw(f)
    self.assertEqual(s, f)
    self.assertEqual(f, t)
    self.assertEqual(t, s)
    self.assertIsInstance(t, set)
