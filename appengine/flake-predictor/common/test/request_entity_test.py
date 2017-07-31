# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import unittest

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from common import request_entity


class RequestEntityTest(unittest.TestCase):

  def setUp(self):
    super(RequestEntityTest, self).setUp()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    # Clear ndb's in-context cache between tests.
    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()
    super(RequestEntityTest, self).tearDown()

  def test_singleton_request_manager_entity(self):
    manager1 = request_entity.RequestManager.load()
    manager2 = request_entity.RequestManager.load()
    self.assertEqual(manager1, manager2)
    self.assertEqual(manager1.key, manager2.key)

  def test_add_requests_to_manager(self):
    e1 = request_entity.Request(status=request_entity.Status.PENDING)
    e2 = request_entity.Request(status=request_entity.Status.RUNNING)
    e3 = request_entity.Request(status=request_entity.Status.COMPLETED)
    # Tests that entity with FAILED status is ignored and not added to pending,
    # running, or completed; therefore, no assertion for this
    e4 = request_entity.Request(status=request_entity.Status.FAILED)
    manager = request_entity.RequestManager.load()
    manager.add_request(e1)
    manager.add_request(e2)
    manager.add_request(e3)
    manager.add_request(e4)
    self.assertEqual(len(manager.pending), 1)
    self.assertEqual(len(manager.running), 1)
    self.assertEqual(len(manager.completed), 1)

  def test_delete_requests_from_manager(self):
    e1 = request_entity.Request(status=request_entity.Status.PENDING)
    e2 = request_entity.Request(status=request_entity.Status.RUNNING)
    e3 = request_entity.Request(status=request_entity.Status.COMPLETED)
    manager = request_entity.RequestManager.load()
    manager.add_request(e1)
    manager.add_request(e2)
    manager.add_request(e3)
    key = manager.save()
    request_entity.RequestManager.delete()
    self.assertEqual(key.get(), None)
    self.assertEqual(manager.pending[0].get(), None)
    self.assertEqual(manager.running[0].get(), None)
    self.assertEqual(manager.completed[0].get(), None)

  def test_save_requests_manager(self):
    e1 = request_entity.Request(status=request_entity.Status.PENDING)
    e2 = request_entity.Request(status=request_entity.Status.RUNNING)
    e3 = request_entity.Request(status=request_entity.Status.COMPLETED)
    manager = request_entity.RequestManager.load()
    manager.add_request(e1)
    manager.add_request(e2)
    manager.add_request(e3)
    key = manager.save()
    self.assertEqual(manager, key.get())
    self.assertEqual(e1, key.get().pending[0].get())
    self.assertEqual(e2, key.get().running[0].get())
    self.assertEqual(e3, key.get().completed[0].get())
