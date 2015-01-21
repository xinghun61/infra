# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from google.appengine.ext import ndb
from testing_utils import testing

from components import auth
from components import utils

from cipd import impl
from cipd import processing


class TestValidators(unittest.TestCase):
  def test_is_valid_package_path(self):
    self.assertTrue(impl.is_valid_package_path('a'))
    self.assertTrue(impl.is_valid_package_path('a/b'))
    self.assertTrue(impl.is_valid_package_path('a/b/c/1/2/3'))
    self.assertTrue(impl.is_valid_package_path('infra/tools/cipd'))
    self.assertTrue(impl.is_valid_package_path('-/_'))
    self.assertFalse(impl.is_valid_package_path(''))
    self.assertFalse(impl.is_valid_package_path('/a'))
    self.assertFalse(impl.is_valid_package_path('a/'))
    self.assertFalse(impl.is_valid_package_path('A'))
    self.assertFalse(impl.is_valid_package_path('a/B'))
    self.assertFalse(impl.is_valid_package_path('a\\b'))

  def test_is_valid_instance_id(self):
    self.assertTrue(impl.is_valid_instance_id('a'*40))
    self.assertFalse(impl.is_valid_instance_id(''))
    self.assertFalse(impl.is_valid_instance_id('A'*40))


class TestRepoService(testing.AppengineTestCase):
  def setUp(self):
    super(TestRepoService, self).setUp()
    self.mocked_cas_service = MockedCASService()
    self.mock(impl.cas, 'get_cas_service', lambda: self.mocked_cas_service)
    self.service = impl.get_repo_service()

  def test_register_package_new(self):
    self.assertIsNone(self.service.get_package('a/b'))
    inst, registered = self.service.register_package(
        package_name='a/b',
        caller=auth.Identity.from_bytes('user:abc@example.com'),
        now=datetime.datetime(2014, 1, 1, 0, 0))
    self.assertTrue(registered)
    self.assertEqual('a/b', inst.package_name)
    self.assertEqual({
      'registered_by': auth.Identity(kind='user', name='abc@example.com'),
      'registered_ts': datetime.datetime(2014, 1, 1, 0, 0)
    }, inst.to_dict())

  def test_register_package_existing(self):
    inst, registered = self.service.register_package(
        package_name='a/b',
        caller=auth.Identity.from_bytes('user:abc@example.com'),
        now=datetime.datetime(2014, 1, 1, 0, 0))
    self.assertTrue(registered)
    inst, registered = self.service.register_package(
        package_name='a/b',
        caller=auth.Identity.from_bytes('user:def@example.com'),
        now=datetime.datetime(2015, 1, 1, 0, 0))
    self.assertFalse(registered)
    self.assertEqual({
      'registered_by': auth.Identity(kind='user', name='abc@example.com'),
      'registered_ts': datetime.datetime(2014, 1, 1, 0, 0)
    }, inst.to_dict())

  def test_register_instance_new(self):
    self.assertIsNone(self.service.get_instance('a/b', 'a'*40))
    self.assertIsNone(self.service.get_package('a/b'))
    inst, registered = self.service.register_instance(
        package_name='a/b',
        instance_id='a'*40,
        caller=auth.Identity.from_bytes('user:abc@example.com'),
        now=datetime.datetime(2014, 1, 1, 0, 0))
    self.assertTrue(registered)
    self.assertEqual(
        ndb.Key('Package', 'a/b', 'PackageInstance', 'a'*40), inst.key)
    self.assertEqual('a/b', inst.package_name)
    self.assertEqual('a'*40, inst.instance_id)
    expected = {
      'registered_by': auth.Identity(kind='user', name='abc@example.com'),
      'registered_ts': datetime.datetime(2014, 1, 1, 0, 0),
      'processors_failure': [],
      'processors_pending': [],
      'processors_success': [],
    }
    self.assertEqual(expected, inst.to_dict())
    self.assertEqual(
        expected, self.service.get_instance('a/b', 'a'*40).to_dict())
    self.assertTrue(self.service.get_package('a/b'))

  def test_register_instance_existing(self):
    # First register a package.
    inst1, registered = self.service.register_instance(
        package_name='a/b',
        instance_id='a'*40,
        caller=auth.Identity.from_bytes('user:abc@example.com'))
    self.assertTrue(registered)
    # Try to register it again.
    inst2, registered = self.service.register_instance(
          package_name='a/b',
          instance_id='a'*40,
          caller=auth.Identity.from_bytes('user:def@example.com'))
    self.assertFalse(registered)
    self.assertEqual(inst1.to_dict(), inst2.to_dict())

  def test_generate_fetch_url(self):
    inst, registered = self.service.register_instance(
        package_name='a/b',
        instance_id='a'*40,
        caller=auth.Identity.from_bytes('user:abc@example.com'),
        now=datetime.datetime(2014, 1, 1, 0, 0))
    self.assertTrue(registered)
    url = self.service.generate_fetch_url(inst)
    self.assertEqual(
        'https://signed-url/SHA1/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', url)

  def test_is_instance_file_uploaded(self):
    self.mocked_cas_service.uploaded.add(('SHA1', 'a'*40))
    self.assertTrue(self.service.is_instance_file_uploaded('a/b', 'a'*40))
    self.assertFalse(self.service.is_instance_file_uploaded('a/b', 'b'*40))

  def test_create_upload_session(self):
    upload_url, upload_session_id = self.service.create_upload_session(
        'a/b', 'a'*40, auth.Identity.from_bytes('user:abc@example.com'))
    self.assertEqual('http://upload_url', upload_url)
    self.assertEqual('upload_session_id', upload_session_id)

  def test_register_instance_with_processing(self):
    self.mock(utils, 'utcnow', lambda: datetime.datetime(2014, 1, 1))

    self.service.processors.append(MockedProcessor('bad', 'Error message'))
    self.service.processors.append(MockedProcessor('good'))

    tasks = []
    def mocked_enqueue_task(**kwargs):
      tasks.append(kwargs)
      return True
    self.mock(impl.utils, 'enqueue_task', mocked_enqueue_task)

    # The processors are added to the pending list.
    inst, registered = self.service.register_instance(
        package_name='a/b',
        instance_id='a'*40,
        caller=auth.Identity.from_bytes('user:abc@example.com'),
        now=datetime.datetime(2014, 1, 1, 0, 0))
    self.assertTrue(registered)
    expected = {
      'registered_by': auth.Identity(kind='user', name='abc@example.com'),
      'registered_ts': datetime.datetime(2014, 1, 1, 0, 0),
      'processors_failure': [],
      'processors_pending': ['bad', 'good'],
      'processors_success': [],
    }
    self.assertEqual(expected, inst.to_dict())

    # The processing task is enqueued.
    self.assertEqual([{
      'payload': '{"instance_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", '
          '"package_name": "a/b", "processors": ["bad", "good"]}',
      'queue_name': 'cipd-process',
      'transactional': True,
      'url': '/internal/taskqueue/cipd-process/'
          'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    }], tasks)

    # Now execute the task.
    self.service.process_instance(
        package_name='a/b',
        instance_id='a'*40,
        processors=['bad', 'good'])

    # Assert the final state.
    inst = self.service.get_instance('a/b', 'a'*40)
    expected = {
      'registered_by': auth.Identity(kind='user', name='abc@example.com'),
      'registered_ts': datetime.datetime(2014, 1, 1, 0, 0),
      'processors_failure': ['bad'],
      'processors_pending': [],
      'processors_success': ['good'],
    }
    self.assertEqual(expected, inst.to_dict())

    good_result = self.service.get_processing_result('a/b', 'a'*40, 'good')
    self.assertEqual({
      'created_ts': datetime.datetime(2014, 1, 1),
      'error': None,
      'result': {
        'instance_id': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        'package_name': 'a/b',
        'processor_name': 'good',
      },
      'success': True,
    }, good_result.to_dict())

    bad_result = self.service.get_processing_result('a/b', 'a'*40, 'bad')
    self.assertEqual({
      'created_ts': datetime.datetime(2014, 1, 1),
      'error': 'Error message',
      'result': None,
      'success': False,
    }, bad_result.to_dict())


class MockedCASService(object):
  def __init__(self):
    self.uploaded = set()

  def is_fetch_configured(self):
    return True

  def generate_fetch_url(self, algo, digest):
    return 'https://signed-url/%s/%s' % (algo, digest)

  def is_object_present(self, algo, digest):
    return (algo, digest) in self.uploaded

  def create_upload_session(self, _algo, _digest, _caller):
    class UploadSession(object):
      upload_url = 'http://upload_url'
    return UploadSession(), 'upload_session_id'


class MockedProcessor(processing.Processor):
  def __init__(self, name, error=None):
    self.name = name
    self.error = error

  def should_process(self, instance):
    return True

  def run(self, instance, data):
    if self.error:
      raise processing.ProcessingError(self.error)
    return {
      'instance_id': instance.instance_id,
      'package_name': instance.package_name,
      'processor_name': self.name,
    }
