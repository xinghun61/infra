# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from testing_utils import testing
from test_results import util


class TestFileHandlerTest(testing.AppengineTestCase):

  def test_already_clean_name(self):
    self.assertEqual('base_unittests', util.normalize_test_type(
        'base_unittests'))

  def test_on_platform(self):
    self.assertEqual('base_unittests', util.normalize_test_type(
        'base_unittests on Windows XP'))

  def test_on_platform_with_patch(self):
    self.assertEqual('base_unittests (with patch)',
        util.normalize_test_type(
            'base_unittests on Windows XP (with patch)'))

  def test_on_platform_with_patch_even_more_noise(self):
    self.assertEqual('base_unittests (with patch)',
        util.normalize_test_type(
            'base_unittests on ATI GPU on Windows (with patch) on Windows'))

  def test_on_platform_with_parens_with_patch_even_more_noise(self):
    self.assertEqual('base_unittests (with patch)',
        util.normalize_test_type(
            'base_unittests (ATI GPU) on Windows (with patch) on Windows'))

  def test_without_patch_is_discarded(self):
    self.assertEqual('base_unittests',
        util.normalize_test_type(
            'base_unittests on ATI GPU on Windows (without patch) on Windows'))

  def test_removes_instrumentation_test_prefix(self):
    self.assertEqual('content_shell_test_apk (with patch)',
        util.normalize_test_type(
            'Instrumentation test content_shell_test_apk (with patch)'))

  def test_ignores_with_patch_when_asked_to(self):
    self.assertEqual('base_unittests', util.normalize_test_type(
        'base_unittests on Windows XP (with patch)',
        ignore_with_patch=True))


class FlattenTestsTrieTest(unittest.TestCase):
  def test_flattens_tests_trie_correctly(self):
    test_trie = {
      'b': {
        'actual': 'FAIL PASS',
        'expected': '...',
      },
      'a': {
        '1': {
          'actual': '...',
          'expected': 'SKIP',
        },
        '2': {
          'actual': '...',
          'expected': '...',
        },
      },
    }

    expected = {
      'b': {
        'actual': ['FAIL', 'PASS'],
        'expected': ['...'],
      },
      'a.1': {
        'actual': ['...'],
        'expected': ['SKIP'],
      },
      'a.2': {
        'actual': ['...'],
        'expected': ['...'],
      },
    }

    actual = util.flatten_tests_trie(test_trie, '.')
    self.assertDictEqual(actual, expected)

