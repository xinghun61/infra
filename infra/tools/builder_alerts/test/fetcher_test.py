# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import timedelta
import json
import unittest

from infra.tools.builder_alerts import fetcher

class RequestCacheTest(unittest.TestCase):
  def test_cache(self):
    c = fetcher.RequestCache(':memory:')
    self.assertFalse(c.has('http://www.google.com'))
    self.assertFalse(c.has('http://www.google.com/?a=1'))
    r0 = fetcher.Response('http://www.google.com',
                          'body text',
                          200, timedelta(seconds=2),
                          cached=False) 
    c.set('http://www.google.com', r0)
    self.assertTrue(c.has('http://www.google.com'))
    self.assertFalse(c.has('http://www.google.com/?a=1'))
    r1 = c.get('http://www.google.com')
    self.assertEqual(r0.url, r1.url)
    self.assertEqual(r0.text, r1.text)
    self.assertEqual(r0.status_code, r1.status_code)
    self.assertEqual(r0.elapsed, r1.elapsed)
    c.delete('http://www.google.com')
    self.assertFalse(c.has('http://www.google.com'))

class ResponseTest(unittest.TestCase):
  def test_json(self):
    obj0 = {'a': 1, 'b': {'c': 'd', 'e': 3}}
    r = fetcher.Response('http://www.google.com',
                         json.dumps(obj0), 200,
                         timedelta(seconds=2))
    obj1 = r.json()
    self.assertEqual(obj0, obj1)

class FetcherTest(unittest.TestCase):
  def test_fetch_cached(self):
    c0 = fetcher.RequestCache(':memory:')
    f = fetcher.Fetcher(c0)
    c1 = fetcher.RequestCache(':memory:')
    r0 = fetcher.Response('http://www.google.com/s%20p%20a%20c%20e?a=b&c=1',
                          'body text', 204,
                          timedelta(seconds=3),
                          cached=False)
    c1.set(r0.url, r0)
    r1 = fetcher.Response('http://www.google.com/?args=included&a=1',
                          'body text again', 400,
                          timedelta(seconds=1), cached=False)
    c1.set(r1.url, r1)
    f.set_cache(c1)
    r0a = f.get('http://www.google.com/s p a c e', {'a': 'b', 'c': 1})
    self.assertEqual(r0.url, r0a.url)
    self.assertEqual(r0.text, r0a.text)
    self.assertTrue(r0a.cached)
    r1a = f.get('http://www.google.com/?args=included', {'a': 1})
    self.assertEqual(r1.url, r1a.url)
    self.assertEqual(r1.text, r1a.text)
    self.assertTrue(r1a.cached)

  def test_global_fetcher(self):
    r0 = fetcher.Response('http://www.google.com', 'body text',
                         200, timedelta(seconds=1))
    fetcher.set_cache(':memory:')
    # pylint: disable=W0212
    fetcher._fetcher.cache.set(r0.url, r0)
    r1 = fetcher.get(r0.url)
    self.assertTrue(r1.cached)
