# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import pickle
import unittest
import zlib

from libs import cache
from libs import cache_decorator


class _DummyCache(cache.Cache):

  def __init__(self, cached_data):
    self.cached_data = cached_data

  def Get(self, key):
    return self.cached_data.get(key)

  def Set(self, key, data, expire_time=0):
    self.cached_data[key] = data


def _DummyKeyGenerator(func, _args, _kwargs, namespace=None):
  namespace = namespace or '%s.%s' % (func.__module__, func.__name__)
  return namespace + '-' + func.__name__


class CachedTest(unittest.TestCase):
  """Tests ``Cached`` decorator."""

  def testDefaultKeyGenerator(self):
    namespace = 'n'
    expected_params = {
        'id1': 'fi',
        'id2': 'pi',
        'url': 'http://url',
    }
    # Hexadecimal digits of MD5 digest of "pickled_params".
    expected_key = namespace + '-f5f173c811f7c537a80d44511903a3e0'

    def MockPickleDumps(params):
      self.assertEqual(expected_params, params)
      return 'pickled_params'

    def func(id1, id2, url=None):  # Unused parameters-pylint: disable=W0613
      return 1  # pragma: no cover.

    class CallableIdentifier(object):

      def identifier(self):
        return 'fi'

    class PropertyIdentifier(object):

      @property
      def identifier(self):
        return 'pi'

    with mock.patch('pickle.dumps', MockPickleDumps):
      args = (CallableIdentifier(), PropertyIdentifier())
      kwargs = {'url': 'http://url'}
      key = cache_decorator._DefaultKeyGenerator(
          func, args, kwargs, namespace=namespace)
      self.assertEqual(expected_key, key)

  def testCachedDecoratorWhenResultIsAlreadyCached(self):
    dummy_cache = _DummyCache({'n-func': 1})

    @cache_decorator.Cached(
        namespace='n', key_generator=_DummyKeyGenerator, cache=dummy_cache)
    def func():
      return 2  # pragma: no cover.

    self.assertEqual(1, func())
    self.assertEqual({'n-func': 1}, dummy_cache.cached_data)

  def testCachedDecoratorWhenResultIsNotCachedYet(self):
    dummy_cache = _DummyCache({})

    @cache_decorator.Cached(
        namespace='n', key_generator=_DummyKeyGenerator, cache=dummy_cache)
    def func():
      return 2

    self.assertEqual(2, func())
    self.assertEqual({'n-func': 2}, dummy_cache.cached_data)

  def testCachedDecoratorWhenResultShouldNotBeCached(self):
    dummy_cache = _DummyCache({})

    results = [None, 0, [], {}, '']

    @cache_decorator.Cached(
        namespace='n', key_generator=_DummyKeyGenerator, cache=dummy_cache)
    def func():
      return results.pop()

    self.assertEqual('', func())
    self.assertEqual({}, dummy_cache.cached_data)
    self.assertEqual({}, func())
    self.assertEqual({}, dummy_cache.cached_data)
    self.assertEqual([], func())
    self.assertEqual({}, dummy_cache.cached_data)
    self.assertEqual(0, func())
    self.assertEqual({}, dummy_cache.cached_data)
    self.assertIsNone(func())
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
      def func(self, path):
        self.runs += 1
        return self.url + '/' + path

    a1 = A('http://test', 3)
    self.assertEqual('http://test/p1', a1.func('p1'))
    self.assertEqual('http://test/p1', a1.func('p1'))
    self.assertEqual(1, a1.runs)

    a2 = A('http://test', 5)
    self.assertEqual('http://test/p1', a2.func('p1'))
    self.assertEqual(0, a2.runs)


class GeneratorCachedTest(unittest.TestCase):
  """Tests ``GeneratorCached`` decorator."""

  def testWhenResultIsAlreadyCached(self):
    value_list = [0, 1, 2]
    key = 'n-func'
    # Zero value won't be cached.
    cached_keys = ['%s-%d' % (key, i) for i in xrange(len(value_list))]
    cached_data = {key: value for key, value in zip(cached_keys, value_list)}
    cached_data[key] = cached_keys

    dummy_cache = _DummyCache(cached_data)

    @cache_decorator.GeneratorCached(
        dummy_cache, namespace='n', key_generator=_DummyKeyGenerator)
    def func():  # pragma: no cover
      for value in value_list:
        yield value

    for value, expected_value in zip(func(), value_list):
      self.assertEqual(value, expected_value)

  def testWhenResultIsNotCachedYet(self):
    value_list = [0, 1, 2, 3, 4]
    dummy_cache = _DummyCache({})

    @cache_decorator.GeneratorCached(
        dummy_cache, namespace='n', key_generator=_DummyKeyGenerator)
    def func():  # pragma: no cover
      for value in value_list:
        yield value

    key = _DummyKeyGenerator(func, [], {}, namespace='n')
    cached_keys = ['%s-%d' % (key, i) for i in xrange(len(value_list))]
    cached_data = {key: value for key, value in zip(cached_keys, value_list)}
    cached_data[key] = cached_keys
    for value, expected_value in zip(func(), value_list):
      self.assertEqual(value, expected_value)

    self.assertDictEqual(dummy_cache.cached_data, cached_data)

  @mock.patch('libs.cache_decorator.GeneratorCached.SetCache', lambda *_: False)
  def testFailedToSetValue(self):
    value_list = [0, 1, 2, 3, 4]
    dummy_cache = _DummyCache({})

    @cache_decorator.GeneratorCached(
        dummy_cache, namespace='n', key_generator=_DummyKeyGenerator)
    def func():  # pragma: no cover
      for value in value_list:
        yield value

    key = _DummyKeyGenerator(func, [], {}, namespace='n')
    cached_keys = ['%s-%d' % (key, i) for i in xrange(len(value_list))]
    cached_data = {key: value for key, value in zip(cached_keys, value_list)}
    cached_data[key] = cached_keys
    for value, expected_value in zip(func(), value_list):
      self.assertEqual(value, expected_value)

    self.assertDictEqual(dummy_cache.cached_data, {})
