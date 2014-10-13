# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class TestName(ndb.Model):
  """A global dict of all known test names, mapped to unique integer keys.

  When a StepResult is stored in the database, its test names are first
  translated to integer keys for storage efficiency.

  Due to the distributed architecture of ndb, it's possible that a test name
  can be duplicated in the global dict (if two app instances both add it at
  the same time).  Rather than try to guarantee uniqueness, this class
  simply allows multiple unique integers to be associated with a single test
  name.  To serve a query over all instances of a test name, the query must
  search for all integers associated with that test name.
  """

  name = ndb.StringProperty('n')

  NAME_CACHE = {}
  NAME_REVERSE_CACHE = {}

  @classmethod
  def _insertCacheEntry(cls, e):
    cls.NAME_CACHE.setdefault(e.name, []).append(e.key.integer_id())
    cls.NAME_REVERSE_CACHE[e.key.integer_id()] = e.name

  @classmethod
  def _guaranteeNameCache(cls):
    if cls.NAME_CACHE:
      return
    q = cls.query()
    q.map(cls._insertCacheEntry)

  @classmethod
  def _addTestName(cls, testName):
    # If the test name was recently added by a different instance of the app,
    # then it will be present in the DB but missing from the cache.
    q = cls.query(cls.name == testName)
    entity = q.get()
    if entity is None:
      first, _ = cls.allocate_ids(1)
      entity = cls(name=testName, key=ndb.Key(cls, first))
      entity.put()
    cls._insertCacheEntry(entity)
    return entity

  @classmethod
  def hasTestName(cls, testName):
    cls._guaranteeNameCache()
    if testName in cls.NAME_CACHE:
      return True
    q = cls.query(cls.name == testName)
    return q.count(1) == 1

  @classmethod
  def getAllKeys(cls, testName):
    """Return all integer keys associated with the testName.

    If the testName is not yet in the database, it will be added.
    """
    cls._guaranteeNameCache()
    if testName not in cls.NAME_CACHE:
      entity = cls._addTestName(testName)
      result = [entity.key.integer_id()]
    else:
      result = cls.NAME_CACHE[testName]
    # AppEngine makes no hard guarantee about the integers it allocates for key
    # ID's, though in practice it increments a counter starting from one.
    # Since we only allot four bytes to store the key ID, let's be safe and
    # check for overflow.
    assert not any([True for x in result if x > 0xffffffff])
    return result

  @classmethod
  def getKey(cls, testName):
    """Return the arbitrary first integer key associated with the testName.

    If the testName is not yet in the database, it will be added.
    """
    return cls.getAllKeys(testName)[0]

  @classmethod
  def getTestName(cls, key):
    """Return the test name associated with an integer key."""
    cls._guaranteeNameCache()
    if key not in cls.NAME_REVERSE_CACHE:
      ndb_key = ndb.Key(cls, key)
      entity = ndb_key.get()
      assert entity
      cls._insertCacheEntry(entity)
    return cls.NAME_REVERSE_CACHE[key]
