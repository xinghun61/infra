# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra.libs import decorators


class TestCachedProperty(unittest.TestCase):
  def setUp(self):
    self.calls = calls = []
    class Foo(object):
      def __init__(self, success=True, override=None):
        self.success = success
        self.override = override

      @decorators.cached_property
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
    self.assertIsInstance(self.Foo.happy, decorators.cached_property)

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

  def testDelRerunsMethodOnce(self):
    f = self.Foo()
    self.assertEqual(f.happy, 'days')
    self.assertEqual(f.happy, 'days')
    del f.happy
    self.assertEqual(f.happy, 'days')
    del f.happy
    del f.happy
    self.assertEqual(f.happy, 'days')
    self.assertEqual(sum(self.calls), 3)
