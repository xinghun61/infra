# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import sys

# App Engine source file imports must be relative to their app's root.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from appengine.utils import testing
from appengine.chromium_cq_status import main
from appengine.chromium_cq_status.model.record import Record
from webtest.app import AppError

class TestPost(testing.AppengineTestCase):
  app_module = main.app
  namespace = '0'

  def _update_namespace(self):
    self.namespace = str(int(self.namespace) + 1)

  def test_post_disallowed(self):
    self.mock_current_user(is_admin=False)

    # 403 status response crashes webtest.
    self.assertRaises(AppError, lambda: self.test_app.post('/post'))

    response = self.test_app.get('/post')
    self.assertEquals('302 Moved Temporarily', response.status)
    self.assertEquals(
      'https://www.google.com/accounts/Login?'
      'continue=http%3A//testbed.example.com/',
      response.location)

  def test_post_single_empty(self):
    self.mock_current_user(is_admin=True)
    self._update_namespace()
    response = self.test_app.get('/post')
    self.assertEquals('Empty record entries disallowed', response.body)
    self.assertEquals(0, Record.query(namespace=self.namespace).count(1))

  def test_post_single_packet(self):
    self.mock_current_user(is_admin=True)
    self._update_namespace()
    response = self.test_app.get('/post', params={
      'project': self.namespace,
      'key': 'test_key',
      'tags': 'tagA,tagB,tagC',
      'fields': '{"some": "random", "json": ["data"]}',
    })
    self.assertEquals('', response.body)
    record = Record.get_by_id('test_key', namespace=self.namespace)
    self.assertTrue(record != None)
    self.assertEquals(set(['tagA', 'tagB', 'tagC']), set(record.tags))
    self.assertEquals({'some': 'random', 'json': ['data']}, record.fields)

  def test_post_single_auto_tagged(self):
    self.mock_current_user(is_admin=True)
    self._update_namespace()
    response = self.test_app.get('/post', params={
      'project': self.namespace,
      'key': 'test_key',
      'tags': 'existingTag,issue=hello',
      'fields': '{"issue": "hello", "patchset": "world"}',
    })
    self.assertEquals('', response.body)
    record = Record.get_by_id('test_key', namespace=self.namespace)
    self.assertTrue(record != None)
    self.assertEquals(
        set(['existingTag', 'issue=hello', 'patchset=world']), set(record.tags))
    self.assertEquals({'issue': 'hello', 'patchset': 'world'}, record.fields)

  def test_post_single_key_update(self):
    self.mock_current_user(is_admin=True)
    self._update_namespace()

    response = self.test_app.get('/post', params={
      'project': self.namespace,
      'key': 'test_key',
    })
    self.assertEquals('', response.body)
    record = Record.get_by_id('test_key', namespace=self.namespace)
    self.assertTrue(record != None)
    self.assertEquals([], record.tags)
    self.assertEquals({}, record.fields)

    response = self.test_app.get('/post', params={
      'project': self.namespace,
      'key': 'test_key',
      'tags': '1,2,3',
      'fields': '{"update": "the", "same": "record"}',
    })
    self.assertEquals('', response.body)
    record = Record.get_by_id('test_key', namespace=self.namespace)
    self.assertTrue(record != None)
    self.assertEquals(set(['1', '2', '3']), set(record.tags))
    self.assertEquals({'update': 'the', 'same': 'record'}, record.fields)

  def test_post_multiple_empty(self):
    self.mock_current_user(is_admin=True)
    self._update_namespace()

    response = self.test_app.post('/post')
    self.assertEquals('', response.body)
    self.assertEquals(0, Record.query(namespace=self.namespace).count(1))

    response = self.test_app.post('/post', params={'p': '{}'})
    self.assertEquals('Empty record entries disallowed', response.body)
    self.assertEquals(0, Record.query(namespace=self.namespace).count(1))

  def test_post_multiple(self):
    self.mock_current_user(is_admin=True)
    self._update_namespace()
    response = self.test_app.post('/post', params=[
      ('p', json.dumps({
        'project': self.namespace,
        'key': 'test_key_0',
        'tags': ['hello', 'world'],
        'fields': {'hello': 'world'},
      })),
      ('p', json.dumps({
        'project': self.namespace,
        'key': 'test_key_1',
        'fields': {'issue': 'autotagged'},
      })),
      ('p', json.dumps({
        'project': self.namespace,
        'key': 'test_key_2',
        'tags': ['empty', 'fields'],
      })),
    ])
    self.assertEquals('', response.body)
    self.assertEquals(3, Record.query(namespace=self.namespace).count(4))

    record = Record.get_by_id('test_key_0', namespace=self.namespace)
    self.assertEquals(set(['hello', 'world']), set(record.tags))
    self.assertEquals({'hello': 'world'}, record.fields)

    record = Record.get_by_id('test_key_1', namespace=self.namespace)
    self.assertEquals(['issue=autotagged'], record.tags)
    self.assertEquals({'issue': 'autotagged'}, record.fields)

    record = Record.get_by_id('test_key_2', namespace=self.namespace)
    self.assertEquals(set(['empty', 'fields']), set(record.tags))
    self.assertEquals({}, record.fields)
