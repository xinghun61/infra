# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import requests

from infra.tools.builder_alerts import reasons_splitter


class MockJsonResponse():
  def __init__(self, data=None, status_code=200):
    self.data = data
    self.status_code = status_code

  def json(self):
    return self.data


k_mock_step = { 'name': 'foo_step' }
k_mock_build = { 'number': 123 }
k_mock_builder_name = 'foo_builder'
k_mock_master_url = 'http://dummydomain.com/foo.master'


class SplitterTests(unittest.TestCase):

  def test_gtest_split_step(self):
    def mock_requests_get(base_url, params):
      # Unused argument - pylint: disable=W0613
      return MockJsonResponse(data={
        'tests': {
          'test1': {'actual': 'PASS', 'expected': 'PASS'},
          'test2': {'actual': 'FAIL', 'expected': 'PASS'},
        }
      })

    old_requests_get = requests.get
    # TODO(ojan): Import httpretty so we don't have to do these try/finally
    # shenanigans.
    try:
      requests.get = mock_requests_get
      failures = reasons_splitter.GTestSplitter.split_step(
          k_mock_step, k_mock_build, k_mock_builder_name, k_mock_master_url)
      self.assertEqual(failures, ['test2'])
    finally:
      requests.get = old_requests_get

  def test_gtest_split_step_404(self):
    def mock_requests_get(base_url, params):
      # Unused argument - pylint: disable=W0613
      return MockJsonResponse(status_code=404)

    old_requests_get = requests.get
    # TODO(ojan): Import httpretty so we don't have to do these try/finally
    # shenanigans.
    try:
      requests.get = mock_requests_get
      failures = reasons_splitter.GTestSplitter.split_step(
          k_mock_step, k_mock_build, k_mock_builder_name, k_mock_master_url)
      self.assertIsNone(failures)
    finally:
      requests.get = old_requests_get

  def test_layout_test_split_step(self):
    def mock_requests_get(base_url, params):
      # Unused argument - pylint: disable=W0613
      return MockJsonResponse(data={
        'tests': {
          'test1': {'actual': 'PASS', 'expected': 'PASS'},
          'test2': {
            'actual': 'FAIL', 'expected': 'PASS', 'is_unexpected': True
          },
        }
      })

    old_requests_get = requests.get
    # TODO(ojan): Import httpretty so we don't have to do these try/finally
    # shenanigans.
    try:
      requests.get = mock_requests_get
      failures = reasons_splitter.LayoutTestsSplitter.split_step(
          { 'name': 'webkit_tests' }, k_mock_build, k_mock_builder_name,
          k_mock_master_url)
      self.assertEqual(failures, {'test2': 'FAIL'})
    finally:
      requests.get = old_requests_get

  def test_layout_test_split_step_404(self):
    def mock_requests_get(base_url, params):
      # Unused argument - pylint: disable=W0613
      return MockJsonResponse(status_code=404)

    old_requests_get = requests.get
    # TODO(ojan): Import httpretty so we don't have to do these try/finally
    # shenanigans.
    try:
      requests.get = mock_requests_get
      failures = reasons_splitter.LayoutTestsSplitter.split_step(
          k_mock_step, k_mock_build, k_mock_builder_name, k_mock_master_url)
      self.assertIsNone(failures)
    finally:
      requests.get = old_requests_get

  def test_failed_tests(self):
    tests = {
      'test1': {'actual': 'PASS', 'expected': 'PASS'},
      'test2': {'actual': 'FAIL', 'expected': 'PASS'},
      'test3': {'actual': 'PASS', 'expected': 'FAIL'},
      'test4': {'actual': 'PASS', 'expected': 'FAIL PASS'},
      'test5': {'actual': 'CRASH', 'expected': 'FAIL PASS'},
      'test6': {'actual': 'CRASH', 'expected': 'CRASH PASS'}
    }
    failed = reasons_splitter.GTestSplitter.failed_tests(tests)
    self.assertFalse('test1' in failed)
    self.assertTrue('test2' in failed)
    self.assertTrue('test3' in failed)
    self.assertFalse('test4' in failed)
    self.assertTrue('test5' in failed)
    self.assertFalse('test6' in failed)

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
                     {'a': { 'actual': '1'}})
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
    self.assertEquals(decode({
                                'a': result('FAIL foo', 'bar'),
                                'b': result('PASS', 'bar'),
                                'c': result('FAIL foo', 'foo'),
                                'd': result('FAIL foo', 'bar')}),
                      {'a': 'FAIL', 'd': 'FAIL'})
    # An unexpected failure is included.
    self.assertEquals(decode({'a': result('FAIL foo', 'bar')}),
                      {'a': 'FAIL'})
    # Failures with multiple results log the first.
    self.assertEquals(decode({'a': result('FAIL foo', 'PASS bar')}),
                      {'a': 'FAIL'})
    # Expected results aren't included.
    self.assertEquals(decode({
                                'a': result('FAIL', 'PASS', False),
                                'b': result('PASS', 'FAIL', False)}),
                      {})
