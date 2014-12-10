#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import suppression_parser

class TestSuppressionParser(unittest.TestCase):
  def test_empty(self):
    self.assertEqual([], suppression_parser.parse(''.splitlines(True)))

  def test_single(self):
    self.assertEqual(['suppression'], suppression_parser.parse("""
Suppressions used:
  count name
      1 suppression""".splitlines(True)))

  def test_other_format(self):
    self.assertEqual(['bug_90013_a',
                      'bug_90013_d',
                      'bug_90013_e'], suppression_parser.parse("""
Suppressions used:
   count    bytes  objects name
      23     4392       61 bug_90013_a
     126    14141      578 bug_90013_d
     299    46428     1830 bug_90013_e
""".splitlines(True)))

  def test_multiple(self):
    self.assertEqual([
        'suppression',
        'bug_1234',
        'dlopen leak on error'], suppression_parser.parse("""
Suppressions used:
  count name
      1 suppression
      2 bug_1234
      2 dlopen leak on error""".splitlines(True)))

  def test_blank_line(self):
    self.assertEqual([
        'suppression',
        'bug_1234',
        'dlopen leak on error'], suppression_parser.parse("""
Suppressions used:
  count name
      1 suppression
      2 bug_1234

      2 dlopen leak on error""".splitlines(True)))

  def test_full(self):
    self.assertEqual([
        'suppression',
        'bug_1234',
        'dlopen leak on error',
        'other one'], suppression_parser.parse("""
some garbage
even more of it
-------------------
Suppressions used:
  count name
      1 suppression
      2 bug_1234
      2 dlopen leak on error
---------------
     99 not a suppression
---------------
garbage
Suppressions used:
  count name
     10 other one
     42 bug_1234
-------------
garbage
even more garbage""".splitlines(True)))


if __name__ == '__main__':
  unittest.main()
