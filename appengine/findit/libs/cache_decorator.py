# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides a decorator to cache the results of a function.

  Examples:
  1. Decorate a function:
    @cache_decorator.Cached()
    def Test(a):
      return a + a

    Test('a')
    Test('a')  # Returns the cached 'aa'.

  2. Decorate a method in a class:
    class Downloader(object):
      def __init__(self, url, retries):
        self.url = url
        self.retries = retries

      @property
      def identifier(self):
        return self.url

      @cache_decorator.Cached():
      def Download(self, path):
        return urllib2.urlopen(self.url + '/' + path).read()

      d1 = Downloader('http://url', 4)
      d1.Download('path')

      d2 = Downloader('http://url', 5)
      d2.Download('path')  # Returned the cached downloaded data.
"""

import functools
import hashlib
import logging
import inspect
import pickle


def _DefaultKeyGenerator(func, args, kwargs, namespace=None):
  """Generates a key from the function and arguments passed to it.

  N.B. ``args`` and ``kwargs`` of function ``func`` should be pickleable,
  or each of the parameter has an ``identifier`` property or method which
  returns pickleable results.

  Args:
    func (function): An arbitrary function.
    args (list): Positional arguments passed to ``func``.
    kwargs (dict): Keyword arguments passed to ``func``.
    namespace (str): A prefix to the key for the cache.

  Returns:
    A string to represent a call to the given function with the given arguments.
  """
  params = inspect.getcallargs(func, *args, **kwargs)
  for var_name in params:
    if not hasattr(params[var_name], 'identifier'):
      continue

    if callable(params[var_name].identifier):
      params[var_name] = params[var_name].identifier()
    else:
      params[var_name] = params[var_name].identifier

  encoded_params = hashlib.md5(pickle.dumps(params)).hexdigest()
  prefix = namespace or '%s.%s' % (func.__module__, func.__name__)

  return '%s-%s' % (prefix, encoded_params)


class CacheDecorator(object):
  """Abstract decorator class to cache the decorated function.

  The usage of this decorator requires that:
  - If the default key generator is used, parameters passed to the decorated
    function should be pickleable, or each of the parameter has an identifier
    property or method which returns pickleable results.
  - If the default cache is used, the returned results of the decorated
    function should be pickleable.
  """

  def __init__(self, cache, namespace=None, expire_time=0,
               key_generator=_DefaultKeyGenerator):
    """
    Args:
      cache (Cache): An instance of an implementation of interface `Cache`.
        Defaults to None.
      namespace (str): A prefix to the key for the cache. Default to the
        combination of module name and function name of the decorated function.
      expire_time (int): Expiration time, relative number of seconds from
        current time (up to 0 month). Defaults to 0 -- never expire.
      key_generator (function): A function to generate a key to represent a call
        to the decorated function. Defaults to :func:`_DefaultKeyGenerator`.
    """
    self._cache = cache
    self._namespace = namespace
    self._expire_time = expire_time
    self._key_generator = key_generator

  def GetCache(self, key, func, args, kwargs):
    """Gets cached result for key.

    Args:
      key (str): The key to retriev result from.
      func (callable): The function to decorate.
      args (iterable): The argument list of the decorated function.
      args (dict): The keyword arguments of the decorated function.

    Returns:
      Returns cached result of key from the ``Cache`` instance.
      N.B. If there is Exception retrieving the cached result, the returned
      result will be set to None.
    """
    try:
      result = self._cache.Get(key)
    except Exception:  # pragma: no cover.
      result = None
      logging.exception(
          'Failed to get cached data for function %s.%s, args=%s, kwargs=%s',
          func.__module__, func.__name__, repr(args), repr(kwargs))

    return result

  def SetCache(self, key, result, func, args, kwargs):
    """Sets result to ``self._cache``.

    Args:
      key (str): The key to retriev result from.
      result (any type): The result of the key.
      func (callable): The function to decorate.
      args (iterable): The argument list of the decorated function.
      args (dict): The keyword arguments of the decorated function.

    Returns:
      Boolean indicating if ``result`` was successfully set or not.
    """
    try:
      self._cache.Set(key, result, expire_time=self._expire_time)
    except Exception:  # pragma: no cover.
      logging.exception(
          'Failed to cache data for function %s.%s, args=%s, kwargs=%s',
          func.__module__, func.__name__, repr(args), repr(kwargs))
      return False

    return True

  def __call__(self, func):
    """Returns a wrapped function of ``func`` which utilize ``self._cache``."""
    raise NotImplementedError()


class Cached(CacheDecorator):
  """Decorator to cache function's results.

  N.B. the decorated function should have return values, because if the function
  returns None, empty list/dict, empty string, or other value that is evaluated
  as False, the results won't be cached.

  This decorator is to cache results of different calls to the decorated
  function, and avoid executing it again if the calls are equivalent. Two calls
  are equivalent, if the namespace is the same and the keys generated by the
  ``key_generator`` are the same.
  """

  def __call__(self, func):
    """Decorator to cache a function's results."""
    @functools.wraps(func)
    def Wrapped(*args, **kwargs):
      key = self._key_generator(func, args, kwargs, namespace=self._namespace)
      cached_result = self.GetCache(key, func, args, kwargs)

      if cached_result is not None:
        return cached_result

      result = func(*args, **kwargs)
      if result:
        self.SetCache(key, result, func, args, kwargs)

      return result

    return Wrapped


class GeneratorCached(CacheDecorator):
  """Decorator to cache a generator function.

  N.B. the decorated function must be a generator which ``yield``s results.

  The key of the generator function will map to a list of sub-keys mapping to
  each element result.N.B. All the results must be cached, no matter it's
  empty or not. If any result failed to be cached, the whole caching is
  considered failed and the key to the generator must NOT be set.

  This decorator is to cache all results of the generator, and ``yield`` them
  one by one from ``self._cache``. Namely, a generator is cached only after it
  was exhausted in a function call. (e.g. a for loop without break statement.)
  """

  def __call__(self, func):
    """Decorator to cache a generator function."""
    @functools.wraps(func)
    def Wrapped(*args, **kwargs):
      key = self._key_generator(func, args, kwargs, namespace=self._namespace)
      cached_keys = self.GetCache(key, func, args, kwargs)

      if cached_keys is not None:
        for cached_key in cached_keys:
          yield self.GetCache(cached_key, func, args, kwargs)
      else:
        result_iter = func(*args, **kwargs)
        result_keys = []

        cache_success = True
        for index, result in enumerate(result_iter):
          yield result
          if not cache_success:
            continue

          result_key = '%s-%d' % (key, index)
          if not self.SetCache(result_key, result, func, args, kwargs):
            cache_success = False
            continue

          result_keys.append(result_key)

        if cache_success:
          self.SetCache(key, result_keys, func, args, kwargs)

    return Wrapped
