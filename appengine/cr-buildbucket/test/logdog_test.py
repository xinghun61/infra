# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import logdog
import v2


class ParseLogDogURLTest(unittest.TestCase):

  def test_success(self):
    url = ('logdog://luci-logdog-dev.appspot.com/'
           'infra/'
           'buildbucket/cr-buildbucket-dev.appspot.com/8952867341410234048/+/'
           'annotations')
    expected = (
        'luci-logdog-dev.appspot.com',
        'infra',
        'buildbucket/cr-buildbucket-dev.appspot.com/8952867341410234048',
        'annotations',
    )
    actual = logdog.parse_url(url)
    self.assertEqual(actual, expected)

  def test_failure(self):
    with self.assertRaises(ValueError):
      logdog.parse_url('logdog://trash')
