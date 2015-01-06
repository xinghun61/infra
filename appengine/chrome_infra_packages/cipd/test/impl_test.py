# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from google.appengine.ext import ndb
from testing_utils import testing

from components import auth

from cipd import impl


class TestValidators(unittest.TestCase):
  def test_is_valid_package_name(self):
    self.assertTrue(impl.is_valid_package_name('a'))
    self.assertTrue(impl.is_valid_package_name('a/b'))
    self.assertTrue(impl.is_valid_package_name('a/b/c/1/2/3'))
    self.assertTrue(impl.is_valid_package_name('infra/tools/cipd'))
    self.assertTrue(impl.is_valid_package_name('-/_'))
    self.assertFalse(impl.is_valid_package_name(''))
    self.assertFalse(impl.is_valid_package_name('/a'))
    self.assertFalse(impl.is_valid_package_name('a/'))
    self.assertFalse(impl.is_valid_package_name('A'))
    self.assertFalse(impl.is_valid_package_name('a/B'))
    self.assertFalse(impl.is_valid_package_name('a\\b'))

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

  @staticmethod
  def fake_signature(key):
    return impl.PackageInstanceSignature(
        hash_algo='SHA1',
        digest='\x00\x01\x02\x03',
        signature_algo='sig algo',
        signature_key=key,
        signature='signature \x00\x01\x02\x03',
        added_by=auth.Identity.from_bytes('user:abc@example.com'),
        added_ts=datetime.datetime(2014, 1, 1))

  def test_register_new(self):
    pkg = self.service.register_instance(
        package_name='a/b',
        instance_id='a'*40,
        signatures=[self.fake_signature('key 1'), self.fake_signature('key 2')],
        caller=auth.Identity.from_bytes('user:abc@example.com'),
        now=datetime.datetime(2014, 1, 1, 0, 0))
    self.assertEqual(
        ndb.Key('Package', 'a/b', 'PackageInstance', 'a'*40), pkg.key)
    expected = {
      'registered_by': auth.Identity(kind='user', name='abc@example.com'),
      'registered_ts': datetime.datetime(2014, 1, 1, 0, 0),
      'signature_keys': ['key 1', 'key 2'],
      'signatures': [
        {
          'added_by': auth.Identity(kind='user', name='abc@example.com'),
          'added_ts': datetime.datetime(2014, 1, 1, 0, 0),
          'digest': '\x00\x01\x02\x03',
          'hash_algo': 'SHA1',
          'signature': 'signature \x00\x01\x02\x03',
          'signature_algo': 'sig algo',
          'signature_key': 'key 1',
        },
        {
          'added_by': auth.Identity(kind='user', name='abc@example.com'),
          'added_ts': datetime.datetime(2014, 1, 1, 0, 0),
          'digest': '\x00\x01\x02\x03',
          'hash_algo': 'SHA1',
          'signature': 'signature \x00\x01\x02\x03',
          'signature_algo': 'sig algo',
          'signature_key': 'key 2',
        },
      ],
    }
    self.assertEqual(expected, pkg.to_dict())
    self.assertEqual(
        expected, self.service.get_instance('a/b', 'a'*40).to_dict())

  def test_register_existing(self):
    # First register a package.
    self.service.register_instance(
        package_name='a/b',
        instance_id='a'*40,
        signatures=[self.fake_signature('key1')],
        caller=auth.Identity.from_bytes('user:abc@example.com'))
    # Try to register it again.
    with self.assertRaises(impl.PackageInstanceExistsError):
      self.service.register_instance(
          package_name='a/b',
          instance_id='a'*40,
          signatures=[],
          caller=auth.Identity.from_bytes('user:abc@example.com'))

  def test_add_signatures_missing(self):
    with self.assertRaises(impl.PackageInstanceNotFoundError):
      self.service.add_signatures('a/b', 'a'*40, [self.fake_signature('key')])

  def test_add_signatures(self):
    self.service.register_instance(
        package_name='a/b',
        instance_id='a'*40,
        signatures=[],
        caller=auth.Identity.from_bytes('user:abc@example.com'))

    expected = lambda key: {
      'added_by': auth.Identity(kind='user', name='abc@example.com'),
      'added_ts': datetime.datetime(2014, 1, 1, 0, 0),
      'digest': '\x00\x01\x02\x03',
      'hash_algo': 'SHA1',
      'signature': 'signature \x00\x01\x02\x03',
      'signature_algo': 'sig algo',
      'signature_key': key,
    }

    # Add one.
    pkg = self.service.add_signatures(
        'a/b', 'a'*40, [self.fake_signature('key0')])
    self.assertEqual([expected('key0')], pkg.to_dict()['signatures'])
    self.assertEqual(['key0'], pkg.to_dict()['signature_keys'])

    # Add exact same one -> no effect.
    pkg = self.service.add_signatures(
        'a/b', 'a'*40, [self.fake_signature('key0')])
    self.assertEqual([expected('key0')], pkg.to_dict()['signatures'])
    self.assertEqual(['key0'], pkg.to_dict()['signature_keys'])

    # Add another one.
    pkg = self.service.add_signatures(
        'a/b', 'a'*40, [self.fake_signature('key1')])
    self.assertEqual(
        [expected('key0'), expected('key1')], pkg.to_dict()['signatures'])
    self.assertEqual(
        ['key0', 'key1'], pkg.to_dict()['signature_keys'])

  def test_is_instance_file_uploaded(self):
    self.mocked_cas_service.uploaded.add(('SHA1', 'a'*40))
    self.assertTrue(self.service.is_instance_file_uploaded('a/b', 'a'*40))
    self.assertFalse(self.service.is_instance_file_uploaded('a/b', 'b'*40))

  def test_create_upload_session(self):
    upload_url, upload_session_id = self.service.create_upload_session(
        'a/b', 'a'*40, auth.Identity.from_bytes('user:abc@example.com'))
    self.assertEqual('http://upload_url', upload_url)
    self.assertEqual('upload_session_id', upload_session_id)


class MockedCASService(object):
  def __init__(self):
    self.uploaded = set()

  def is_object_present(self, algo, digest):
    return (algo, digest) in self.uploaded

  def create_upload_session(self, _algo, _digest, _caller):
    class UploadSession(object):
      upload_url = 'http://upload_url'
    return UploadSession(), 'upload_session_id'
