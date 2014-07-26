# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import textwrap

from infra.libs.git2 import util


class TestInvalid(unittest.TestCase):
  def testBasic(self):
    self.assertIs(util.INVALID, util.INVALID)
    self.assertIs(util.INVALID.bob, util.INVALID)
    self.assertIs(util.INVALID('cat', dog='food'), util.INVALID)
    self.assertTrue(not (util.INVALID == util.INVALID))
    self.assertNotEqual(util.INVALID, util.INVALID)


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
