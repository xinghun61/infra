# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import shutil
import tempfile
import unittest

from infra.tools.builder_alerts import buildbot


class BuildCacheTest(unittest.TestCase):
  def setUp(self):
    self.cache_path = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.cache_path, ignore_errors=True)

  def test_build_cache(self):
    cache = buildbot.BuildCache(self.cache_path)

    test_key = 'foo/bar'
    self.assertFalse(cache.has(test_key))

    test_data = ['test']
    cache.set(test_key, test_data)
    # Set it a second time to hit the "already there" case.
    cache.set(test_key, test_data)

    self.assertTrue(cache.has(test_key))
    self.assertEquals(cache.get(test_key), test_data)

    self.assertIsNone(cache.get('does_not_exist'))
    self.assertIsNotNone(cache.key_age(test_key))


class BuildbotTest(unittest.TestCase):
  def test_master_name_from_url(self):
    tests = [
      ('https://build.chromium.org/p/chromium.mac', 'chromium.mac'),
      ('https://build.chromium.org/p/tryserver.blink', 'tryserver.blink')
    ]
    for master_url, master_name in tests:
      self.assertEquals(buildbot.master_name_from_url(master_url), master_name)

  def test_build_url(self):
    url = buildbot.build_url('https://foo.com/p/bar', 'baz', '12')
    self.assertEquals(url, 'https://foo.com/p/bar/builders/baz/builds/12')

  def test_cache_key_for_build(self):
    key = buildbot.cache_key_for_build('master', 'builder', 10)
    self.assertEquals(key, 'master/builder/10.json')

  def test_is_in_progress(self):
    self.assertEqual(buildbot.is_in_progress({'results': None}), True)
    self.assertEqual(buildbot.is_in_progress({'results': 2}), False)
