# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from appengine_module.testing_utils import testing
from appengine_module.test_results.handlers import util


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
