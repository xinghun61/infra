# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.iterator import Iterate
from gae_libs.testcase import TestCase

from google.appengine.ext import ndb


class _Entity(ndb.Model):
  index = ndb.IntegerProperty(indexed=True)


class IteratorTest(TestCase):

  def testIterateWhenThereAreNoEntities(self):
    """Tests ``Iterate`` when there are no entities."""
    query = _Entity.query().order(_Entity.index)
    entities = [entity for entity in Iterate(query, batch_run=False)]
    self.assertEqual(entities, [])

  def testIterateByEntity(self):
    """Tests that ``Iterate`` iterates every entity."""
    entities = [_Entity(), _Entity(), _Entity()]
    for index, entity in enumerate(entities):
      entity.index = index

    ndb.put_multi(entities)

    query = _Entity.query().order(_Entity.index)
    for index, entity in enumerate(Iterate(query, batch_run=False)):
      self.assertEqual(entity.index, index)

    for index, entity in enumerate(
        Iterate(query, batch_size=1, batch_run=False)):
      self.assertEqual(entity.index, index)

  def testIterateByEntityBatch(self):
    """Tests that ``Iterate`` iterates batches of entities."""
    entities = [_Entity(), _Entity(), _Entity(), _Entity()]
    for index, entity in enumerate(entities):
      entity.index = index

    ndb.put_multi(entities)

    query = _Entity.query().order(_Entity.index)
    batch_size = 2
    iterated_entities = []
    for entity_batch in Iterate(query, batch_size=batch_size, batch_run=True):
      self.assertTrue(len(entity_batch) <= batch_size)
      iterated_entities.extend(entity_batch)

    self.assertListEqual(iterated_entities, entities)
