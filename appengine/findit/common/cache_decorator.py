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

import cStringIO
import functools
import hashlib
import inspect
import logging
import pickle
import zlib

from google.appengine.api import memcache


class Cacher(object):
  """An interface to cache and retrieve data.

  Subclasses should implement the Get/Set functions.
  TODO: Add a Delete function (default to no-op) if needed later.
  """
  def Get(self, key):
    """Returns the cached data for the given key if available.

    Args:
      key (str): The key to identify the cached data.
    """
    raise NotImplementedError()

  def Set(self, key, data, expire_time=0):
    """Cache the given data which is identified by the given key.

    Args:
      key (str): The key to identify the cached data.
      data (object): The python object to be cached.
      expire_time (int): Number of seconds from current time (up to 1 month).
    """
    raise NotImplementedError()


class PickledMemCacher(Cacher):
  """A memcache-backed implementation of the interface Cacher.

  The data to be cached should be pickleable.
  Limitation: size of the pickled data and key should be <= 1MB.
  """
  def Get(self, key):
    return memcache.get(key)

  def Set(self, key, data, expire_time=0):
    return memcache.set(key, data, time=expire_time)


class _CachedItemMetaData(object):
  def __init__(self, number):
    self.number = number


class CompressedMemCacher(Cacher):
  """A memcache-backed implementation of the interface Cacher with compression.

  The data to be cached would be pickled and then compressed.
  Data still > 1MB will be split into sub-piece and stored separately.
  During retrieval, if any sub-piece is missing, None is returned.
  """
  CHUNK_SIZE = 990000

  def Get(self, key):
    data = memcache.get(key)
    if isinstance(data, _CachedItemMetaData):
      num = data.number
      sub_keys = ['%s-%s' % (key, i) for i in range(num)]
      all_data = memcache.get_multi(sub_keys)
      if len(all_data) != num:  # Some data is missing.
        return None

      data_output = cStringIO.StringIO()
      for sub_key in sub_keys:
        data_output.write(all_data[sub_key])
      data = data_output.getvalue()

    return None if data is None else pickle.loads(zlib.decompress(data))

  def Set(self, key, data, expire_time=0):
    pickled_data = pickle.dumps(data)
    compressed_data = zlib.compress(pickled_data)

    all_data = {}
    if len(compressed_data) > self.CHUNK_SIZE:
      num = 0
      for index in range(0, len(compressed_data), self.CHUNK_SIZE):
        sub_key = '%s-%s' % (key, num)
        all_data[sub_key] = compressed_data[index : index + self.CHUNK_SIZE]
        num += 1

      all_data[key] = _CachedItemMetaData(num)
    else:
      all_data[key] = compressed_data

    keys_not_set = memcache.set_multi(all_data, time=expire_time)
    return len(keys_not_set) == 0


def _DefaultKeyGenerator(func, args, kwargs):
  """Generates a key from the function and arguments passed to it.

  Args:
    func (function): An abitrary function.
    args (list): Positional arguments passed to ``func``.
    kwargs (dict): Keyword arguments passed to ``func``.

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

  return hashlib.md5(pickle.dumps(params)).hexdigest()


def Cached(namespace=None,
           expire_time=0,
           key_generator=_DefaultKeyGenerator,
           cacher=PickledMemCacher()):
  """Returns a decorator to cache the decorated function's results.

  However, if the function returns None, empty list/dict, empty string, or other
  value that is evaluated as False, the results won't be cached.

  This decorator is to cache results of different calls to the decorated
  function, and avoid executing it again if the calls are equivalent. Two calls
  are equivalent, if the namespace is the same and the keys generated by the
  ``key_generator`` are the same.

  The usage of this decorator requires that:
  - If the default key generator is used, parameters passed to the decorated
    function should be pickleable, or each of the parameter has an identifier
    property or method which returns pickleable results.
  - If the default cacher is used, the returned results of the decorated
    function should be pickleable.

  Args:
    namespace (str): A prefix to the key for the cache. Default to the
        combination of module name and function name of the decorated function.
    expire_time (int): Expiration time, relative number of seconds from current
        time (up to 1 month). Defaults to 0 -- never expire.
    key_generator (function): A function to generate a key to represent a call
        to the decorated function. Defaults to :func:`_DefaultKeyGenerator`.
    cacher (Cacher): An instance of an implementation of interface `Cacher`.
        Defaults to one of `PickledMemCacher` which is based on memcache.

  Returns:
    The cached results or the results of a new run of the decorated function.
  """
  def GetPrefix(func, namespace):
    return namespace or '%s.%s' % (func.__module__, func.__name__)

  def Decorator(func):
    """Decorator to cache a function's results."""
    @functools.wraps(func)
    def Wrapped(*args, **kwargs):
      prefix = GetPrefix(func, namespace)
      key = '%s-%s' % (prefix, key_generator(func, args, kwargs))

      try:
        result = cacher.Get(key)
      except Exception:  # pragma: no cover.
        result = None
        logging.exception(
            'Failed to get cached data for function %s.%s, args=%s, kwargs=%s',
            func.__module__, func.__name__, repr(args), repr(kwargs))

      if result is not None:
        return result

      result = func(*args, **kwargs)
      if result:
        try:
          cacher.Set(key, result, expire_time=expire_time)
        except Exception:  # pragma: no cover.
          logging.exception(
              'Failed to cache data for function %s.%s, args=%s, kwargs=%s',
              func.__module__, func.__name__, repr(args), repr(kwargs))

      return result

    return Wrapped

  return Decorator
