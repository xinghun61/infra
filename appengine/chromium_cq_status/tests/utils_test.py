# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import os

# App Engine source file imports must be relative to their app's root.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from appengine.utils import testing
from appengine.chromium_cq_status.shared import utils

class TestUtils(testing.AppengineTestCase):
  def test_filter_dict(self):
    self.assertEquals(
        {'b': 2, 'c': 3},
        utils.filter_dict({'a': 1, 'b': 2, 'c': 3}, ('b', 'c', 'd')))

  def test_is_valid_user(self):
    self.assertFalse(utils.is_valid_user())

    self.mock_current_user('random', 'random@person.com')
    self.assertFalse(utils.is_valid_user())

    self.mock_current_user('real', 'real@chromium.org')
    self.assertTrue(utils.is_valid_user())

    self.mock_current_user('real', 'real@google.com')
    self.assertTrue(utils.is_valid_user())

    self.mock_current_user('fake', 'fake@google.comm')
    self.assertFalse(utils.is_valid_user())

    self.mock_current_user('fake', 'fake@chromium.orgg')
    self.assertFalse(utils.is_valid_user())

  def test_password_sha1(self):
    self.assertEquals(
        '018d644a17b71b65cef51fa0a523a293f2b3266f',
        utils.password_sha1('cq'))
