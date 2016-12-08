# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pickle
import zlib

from testing_utils import testing

from libs import cache
from libs import cache_decorator


class _DummyCache(cache.Cache):
  def __init__(self, cached_data):
    self.cached_data = cached_data

  def Get(self, key):
    return self.cached_data.get(key)

  def Set(self, key, data, expire_time=0):
    self.cached_data[key] = data


def _DummyKeyGenerator(func, *_):
  return func.__name__


class CacheDecoratorTest(testing.AppengineTestCase):
  def testDefaultKeyGenerator(self):
    expected_params = {
        'id1': 'fi',
        'id2': 'pi',
        'url': 'http://url',
    }
    # Hexadecimal digits of MD5 digest of "pickled_params".
    expected_key = 'f5f173c811f7c537a80d44511903a3e0'

    def MockPickleDumps(params):
      self.assertEqual(expected_params, params)
      return 'pickled_params'

    def Func(id1, id2, url=None):  # Unused parameters-pylint: disable=W0613
      return 1  # pragma: no cover.

    class CallableIdentifier(object):
      def identifier(self):
        return 'fi'

    class PropertyIdentifier(object):
      @property
      def identifier(self):
        return 'pi'

    self.mock(pickle, 'dumps', MockPickleDumps)

    args = (CallableIdentifier(), PropertyIdentifier())
    kwargs = {'url': 'http://url'}
    key = cache_decorator._DefaultKeyGenerator(Func, args, kwargs)
    self.assertEqual(expected_key, key)

  def testCachedDecoratorWhenResultIsAlreadyCached(self):
    dummy_cache = _DummyCache({'n-Func': 1})

    @cache_decorator.Cached(
        namespace='n', key_generator=_DummyKeyGenerator, cache=dummy_cache)
    def Func():
      return 2  # pragma: no cover.

    self.assertEqual(1, Func())
    self.assertEqual({'n-Func': 1}, dummy_cache.cached_data)

  def testCachedDecoratorWhenResultIsNotCachedYet(self):
    dummy_cache = _DummyCache({})

    @cache_decorator.Cached(
        namespace='n', key_generator=_DummyKeyGenerator, cache=dummy_cache)
    def Func():
      return 2

    self.assertEqual(2, Func())
    self.assertEqual({'n-Func': 2}, dummy_cache.cached_data)

  def testCachedDecoratorWhenResultShouldNotBeCached(self):
    dummy_cache = _DummyCache({})

    results = [None, 0, [], {}, '']

    @cache_decorator.Cached(
        namespace='n', key_generator=_DummyKeyGenerator, cache=dummy_cache)
    def Func():
      return results.pop()

    self.assertEqual('', Func())
    self.assertEqual({}, dummy_cache.cached_data)
    self.assertEqual({}, Func())
    self.assertEqual({}, dummy_cache.cached_data)
    self.assertEqual([], Func())
    self.assertEqual({}, dummy_cache.cached_data)
    self.assertEqual(0, Func())
    self.assertEqual({}, dummy_cache.cached_data)
    self.assertIsNone(Func())
    self.assertEqual({}, dummy_cache.cached_data)

  def testCachedDecoratorWithMethodInAClass(self):
    class A(object):
      def __init__(self, url, retries):
        self.url = url
        self.retries = retries
        self.runs = 0

      @property
      def identifier(self):
        return self.url

      @cache_decorator.Cached(cache=_DummyCache({}))
      def Func(self, path):
        self.runs += 1
        return self.url + '/' + path

    a1 = A('http://test', 3)
    self.assertEqual('http://test/p1', a1.Func('p1'))
    self.assertEqual('http://test/p1', a1.Func('p1'))
    self.assertEqual(1, a1.runs)

    a2 = A('http://test', 5)
    self.assertEqual('http://test/p1', a2.Func('p1'))
    self.assertEqual(0, a2.runs)
