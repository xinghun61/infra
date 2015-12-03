# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb

from testing_utils import testing

from model.versioned_model import VersionedModel


class _Entity(VersionedModel):
  value = ndb.IntegerProperty(indexed=False)


class VersionedModelTest(testing.AppengineTestCase):
  def testGetRootModel(self):
    root_model_class = _Entity._GetRootModel()
    self.assertEqual('_EntityRoot', root_model_class._get_kind())
    self.assertTrue(issubclass(root_model_class, ndb.Model))
    self.assertEqual(3, root_model_class(current=3).current)

  def testGetMostRecentVersionWhenNoData(self):
    entity = _Entity.GetMostRecentVersion()
    self.assertIsNone(entity)

  def testGetMostRecentVersionWhenDataExists(self):
    root_key = ndb.Key('_EntityRoot', 1)
    _Entity._GetRootModel()(key=root_key, current=2).put()
    _Entity(key=ndb.Key('_Entity', 1, parent=root_key), value=1).put()
    _Entity(key=ndb.Key('_Entity', 2, parent=root_key), value=2).put()

    entity = _Entity.GetMostRecentVersion()
    self.assertEqual(2, entity.version)
    self.assertEqual(2, entity.value)

  def testSaveNewVersion(self):
    entity = _Entity()
    entity.value = 1
    key = entity.Save()

    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 1)
    self.assertEqual(expected_key, key)

    entity = _Entity.GetMostRecentVersion()
    self.assertEqual(1, entity.version)
    self.assertEqual(1, entity.value)

  def testSaveNewVersionAlreadyExist(self):
    original_ndb_transaction = ndb.transaction

    def MockNdbTransaction(func, **options):
      _Entity(key=ndb.Key('_EntityRoot', 1, '_Entity', 1), value=1).put()
      _Entity(key=ndb.Key('_EntityRoot', 1, '_Entity', 2), value=2).put()
      return original_ndb_transaction(func, **options)
    self.mock(ndb, 'transaction', MockNdbTransaction)

    entity = _Entity()
    key = entity.Save()
    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 3)
    self.assertEqual(expected_key, key)

  def testLikelyTransactionFailure(self):
    original_ndb_transaction = ndb.transaction

    calls = []
    def MockNdbTransaction(func, **options):
      if len(calls) < 1:
        calls.append(1)
        raise datastore_errors.Timeout()
      return original_ndb_transaction(func, **options)
    self.mock(ndb, 'transaction', MockNdbTransaction)

    entity = _Entity()
    key = entity.Save()
    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 1)
    self.assertEqual(expected_key, key)
    self.assertEqual([1], calls)

  def testTransactionFailure(self):
    original_ndb_transaction = ndb.transaction

    calls = []
    def MockNdbTransaction(func, **options):
      if len(calls) < 1:
        calls.append(1)
        raise datastore_errors.BadRequestError()
      return original_ndb_transaction(func, **options)
    self.mock(ndb, 'transaction', MockNdbTransaction)

    entity = _Entity()
    key = entity.Save()
    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 1)
    self.assertEqual(expected_key, key)
    self.assertEqual([1], calls)
