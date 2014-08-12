# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra.tools.builder_alerts import reasons_splitter


class SplitterTests(unittest.TestCase):
  def test_handles_step(self):
    name_tests = [
      ('compile', reasons_splitter.CompileSplitter),
      ('webkit_tests', reasons_splitter.LayoutTestsSplitter),
      ('androidwebview_instrumentation_tests', reasons_splitter.JUnitSplitter),
      ('foo_tests', reasons_splitter.GTestSplitter),
      ('foo_test', None),
    ]
    for step_name, expected_class in name_tests:
      splitter = reasons_splitter.splitter_for_step({'name': step_name})
      if expected_class is None:
        self.assertIsNone(splitter)
      else:
        self.assertEqual(splitter.__class__, expected_class)

  def test_flatten_trie(self):
    flatten = reasons_splitter.flatten_test_results
    self.assertEqual(flatten({}), {})
    self.assertEqual(flatten({'a': {}}), {'a': {}})
    # prefixes are applied correctly
    self.assertEqual(flatten({'a': {}}, 'foo'), {'foo/a': {}})
    # single-component names flatten to themselves
    self.assertEqual(flatten({'a': {'actual': '1'}}),
                     {'a': { 'actual': '1'}}),
    # >1 component names flatten properly
    self.assertEqual(flatten({'a': {'b': {'actual': '3'}}}),
                     {'a/b': {'actual': '3'}})
    # actual/expected nodes flatten properly
    self.assertEqual(flatten({'a': {'actual': '1', 'expected': '2'},
                              'd': {'actual': '3'}}),
                     {'a': {'actual': '1', 'expected': '2'},
                      'd': {'actual': '3'}})
    # actual/expected terminate recursion
    self.assertEqual(flatten({'a':
                               {'b': {'actual': '1', 'expected': '2'},
                                'c': {'actual': '3',
                                      'expected': '4',
                                      'd': {'actual': '5'}
                                     }
                               }
                             }),
                     {
                       'a/b': {'actual': '1', 'expected': '2'},
                       'a/c': {'actual': '3',
                               'd': {'actual': '5'},
                               'expected': '4'},
                     })

  def test_decode_results(self):
    decode = reasons_splitter.decode_results
    def result(actual, expected, unexpected=True):
      return {'actual': actual,
              'expected': expected,
              'is_unexpected': unexpected}
    # unexpected results are included
    self.assertEquals(decode({'tests': {
                                'a': result('FAIL foo', 'bar'),
                                'b': result('PASS', 'bar'),
                                'c': result('FAIL foo', 'foo'),
                                'd': result('FAIL foo', 'bar')}}),
                     ({'b': result('PASS', 'bar')},
                      {'a': 'FAIL', 'd': 'FAIL'},
                      {'c': 'FAIL'}))
    # An unexpected failure is included.
    self.assertEquals(decode({'tests': {'a': result('FAIL foo', 'bar')}}),
                      ({}, {'a': 'FAIL'}, {}))
    # An unexpected success is included.
    self.assertEquals(decode({'tests': {'a': result('PASS', 'bar')}}),
                      ({'a': result('PASS', 'bar')}, {}, {}))
    # Flakes are included.
    self.assertEquals(decode({'tests': {'a': result('FAIL foo', 'foo')}}),
                      ({}, {}, {'a': 'FAIL'}))
    # Failures with multiple results log the first.
    self.assertEquals(decode({'tests': {'a': result('FAIL foo', 'PASS bar')}}),
                      ({}, {'a': 'FAIL'}, {}))
    # Expected results aren't included by default...
    self.assertEquals(decode({'tests': {
                                'a': result('FAIL', 'PASS', False),
                                'b': result('PASS', 'FAIL', False)}}),
                      ({}, {}, {}))
    # ...but can be
    self.assertEquals(decode({'tests': {'a': result('FAIL', 'PASS', False)}},
                             True),
                      ({}, {'a': 'FAIL'}, {}))
