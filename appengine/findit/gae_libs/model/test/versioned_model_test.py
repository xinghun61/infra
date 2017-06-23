# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb

from testing_utils import testing

from gae_libs.model.versioned_model import VersionedModel


class _Entity(VersionedModel):
  value = ndb.IntegerProperty(indexed=False)


class VersionedModelTest(testing.AppengineTestCase):

  def testGetRootModel(self):
    root_model_class = _Entity._GetRootModel()
    self.assertEqual('_EntityRoot', root_model_class._get_kind())
    self.assertTrue(issubclass(root_model_class, ndb.Model))
    self.assertEqual(3, root_model_class(current=3).current)

  def testDefaultVersionIsZero(self):
    self.assertEqual(0, _Entity.Create().version_number)
    self.assertEqual(0, _Entity.Create('m1').version_number)

  def testRootId(self):
    self.assertEqual(1, _Entity.Create()._root_id)
    self.assertEqual(
        1, _Entity(key=ndb.Key('_EntityRoot', 1, '_Entity', 2))._root_id)
    self.assertEqual('m1', _Entity.Create('m1')._root_id)

  def testCreate(self):
    self.assertEqual(
        _Entity(key=ndb.Key('_EntityRoot', 'm1', '_Entity', 0)),
        _Entity.Create('m1'))

  def testGetMostRecentVersionWhenNoData(self):
    self.assertIsNone(_Entity.GetVersion())
    self.assertIsNone(_Entity.GetVersion('m1'))

  def testGetMostRecentVersionWhenDataExists(self):
    entity = _Entity.Create()
    entity.value = 1
    entity.Save()
    entity.value = 2
    entity.Save()

    entity = _Entity.GetVersion()
    self.assertEqual(2, entity.version_number)
    self.assertEqual(2, entity.value)

  def testGetSpecificVersion(self):
    entity = _Entity.Create()
    entity.value = 1
    entity.Save()
    entity.value = 2
    entity.Save()

    entity_version_2 = _Entity.GetVersion(version=2)
    self.assertEqual(2, entity_version_2.version_number)
    self.assertEqual(2, entity_version_2.value)
    self.assertIsNone(_Entity.GetVersion(version=0))
    self.assertIsNone(_Entity.GetVersion(version=3))

  def testGetLatestVersionNumber(self):
    entity = _Entity.Create()
    entity.Save()
    self.assertEqual(1, _Entity.GetLatestVersionNumber())

  def testGetVersionForEntityWithKeyId(self):
    entity = _Entity.Create('m1')
    entity.value = 1
    entity.Save()
    entity.value = 2
    entity.Save()

    self.assertEqual(2, _Entity.GetVersion('m1').version_number)
    self.assertEqual(2, _Entity.GetVersion('m1').value)
    self.assertIsNone(_Entity.GetVersion('m1', version=0))
    self.assertIsNone(_Entity.GetVersion('m1', version=3))

  def testGetLatestVersionNumberWhenNoRecordYet(self):
    self.assertEqual(-1, _Entity.GetLatestVersionNumber())
    self.assertEqual(-1, _Entity.GetLatestVersionNumber('m1'))

  def testSaveNewVersion(self):
    entity = _Entity.Create()
    entity.value = 1
    key, saved = entity.Save()

    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 1)
    self.assertEqual(expected_key, key)
    self.assertTrue(saved)

    entity = _Entity.GetVersion()
    self.assertEqual(1, entity.version_number)
    self.assertEqual(1, entity.value)

  def testSaveEntityWithRootId(self):
    entity = _Entity.Create('m1')
    entity.value = 1
    entity.Save()
    entity.value = 3
    entity.Save()

    self.assertEqual(entity.version_number, 2)
    self.assertEqual(entity.value, 3)

  def testSaveNewVersionOfEntityWithKeyId(self):
    entity = _Entity.Create('m1')
    entity.value = 1
    key, saved = entity.Save()
    expected_key = ndb.Key('_EntityRoot', 'm1', '_Entity', 1)
    self.assertEqual(expected_key, key)
    self.assertTrue(saved)

  def testSaveNewVersionWithConflictRetry(self):
    original_ndb_transaction = ndb.transaction

    def MockNdbTransaction(func, **options):
      _Entity(key=ndb.Key('_EntityRoot', 1, '_Entity', 1), value=1).put()
      _Entity(key=ndb.Key('_EntityRoot', 1, '_Entity', 2), value=2).put()
      return original_ndb_transaction(func, **options)

    self.mock(ndb, 'transaction', MockNdbTransaction)

    entity = _Entity.Create()
    key, saved = entity.Save()
    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 3)
    self.assertEqual(expected_key, key)
    self.assertTrue(saved)

  def testSaveNewVersionWithConflictBeforeTransactionNoRetry(self):
    original_ndb_transaction = ndb.transaction

    def MockNdbTransaction(func, **options):
      # To simulate another transaction occuring before this one, write a new
      # version first before the transaction is called.
      _Entity(key=ndb.Key('_EntityRoot', 1, '_Entity', 1), value=1).put()
      return original_ndb_transaction(func, **options)

    self.mock(ndb, 'transaction', MockNdbTransaction)

    entity = _Entity.Create()
    key, saved = entity.Save(retry_on_conflict=False)
    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 1)
    self.assertEqual(expected_key, key)
    self.assertFalse(saved)

  def testSaveNewVersionConflictBeforeSaving(self):
    original_save = VersionedModel.Save

    def MockSave(*args, **kwargs):
      # Smulate another transaction beating this call to Save() to creating a
      # new entity.
      _Entity(key=ndb.Key('_EntityRoot', 1, '_Entity', 1), value=1).put()
      return original_save(*args, **kwargs)

    self.mock(VersionedModel, 'Save', MockSave)

    entity = _Entity.Create()
    key, saved = entity.Save(retry_on_conflict=False)
    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 1)
    self.assertEqual(expected_key, key)
    self.assertFalse(saved)

  def testLikelyTransactionFailure(self):
    original_ndb_transaction = ndb.transaction

    calls = []

    def MockNdbTransaction(func, **options):
      if len(calls) < 1:
        calls.append(1)
        raise datastore_errors.Timeout()
      return original_ndb_transaction(func, **options)

    self.mock(ndb, 'transaction', MockNdbTransaction)

    entity = _Entity.Create()
    key, saved = entity.Save()
    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 1)
    self.assertEqual(expected_key, key)
    self.assertTrue(saved)
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

    entity = _Entity.Create()
    key, saved = entity.Save()
    expected_key = ndb.Key('_EntityRoot', 1, '_Entity', 1)
    self.assertEqual(expected_key, key)
    self.assertEqual([1], calls)
    self.assertTrue(saved)
