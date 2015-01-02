# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from testing_utils import testing

from components import auth
from components import auth_testing
from components import utils

from cipd import api
from cipd import impl


class TestSerialization(testing.AppengineTestCase):
  def test_signature_from_entity(self):
    ent = impl.PackageInstanceSignature(
        hash_algo='SHA1',
        digest='\x00\x01\x02\x03\x04\x05',
        signature_algo='sig algo',
        signature_key='sig key',
        signature='signature \x00\x01\x02\x03\x04\x05',
        added_by=auth.Identity.from_bytes('user:abc@example.com'),
        added_ts=datetime.datetime(2014, 1, 1))
    msg = api.signature_from_entity(ent)
    self.assertEqual('SHA1', msg.hash_algo)
    self.assertEqual('\x00\x01\x02\x03\x04\x05', msg.digest)
    self.assertEqual('sig algo', msg.signature_algo)
    self.assertEqual('sig key', msg.signature_key)
    self.assertEqual('signature \x00\x01\x02\x03\x04\x05', msg.signature)
    self.assertEqual('user:abc@example.com', msg.added_by)
    self.assertEqual(1388534400000000, msg.added_ts)

  def test_signature_to_entity(self):
    msg = api.Signature(
        hash_algo='SHA1',
        digest='\x00\x01\x02\x03\x04\x05',
        signature_algo='sig algo',
        signature_key='sig key',
        signature='signature \x00\x01\x02\x03\x04\x05',
        added_by='user:abc@example.com',
        added_ts=1388534400000000)
    ent = api.signature_to_entity(msg)
    # Ignores added_* fields, they are output only.
    expected = {
      'hash_algo': 'SHA1',
      'digest': '\x00\x01\x02\x03\x04\x05',
      'signature_algo': 'sig algo',
      'signature_key': 'sig key',
      'signature': 'signature \x00\x01\x02\x03\x04\x05',
      'added_by': None,
      'added_ts': None,
    }
    self.assertEqual(expected, ent.to_dict())


class PackageRepositoryApiTest(testing.EndpointsTestCase):
  """Tests for API layer ONLY."""

  api_service_cls = api.PackageRepositoryApi

  def setUp(self):
    super(PackageRepositoryApiTest, self).setUp()
    auth_testing.mock_get_current_identity(self)
    auth_testing.mock_is_admin(self)
    self.repo_service = MockedRepoService()
    self.mock(impl, 'get_repo_service', lambda: self.repo_service)

  def test_register_new_package_flow(self):
    self.mock(utils, 'utcnow', lambda: datetime.datetime(2014, 1, 1))
    request = {
      'package_name': 'good/name',
      'instance_id': 'a'*40,
      'signatures': [
        {
          'hash_algo': 'SHA1',
          'digest': 'AAECAwQ=',
          'signature_algo': 'sig algo',
          'signature_key': 'sig key 1',
          'signature': 'c2lnbmF0dXJlIAABAgME',
        },
        {
          'hash_algo': 'SHA1',
          'digest': 'AAECAwQ=',
          'signature_algo': 'sig algo',
          'signature_key': 'sig key 2',
          'signature': 'c2lnbmF0dXJlIAABAgME',
        },
      ],
    }

    # Package is not uploaded yet. Should ask to upload.
    resp = self.call_api('register_package', request)
    self.assertEqual(200, resp.status_code)
    self.assertEqual({
      'status': 'UPLOAD_FIRST',
      'upload_session_id': 'upload_session_id',
      'upload_url': 'http://upload_url',
    }, resp.json_body)

    # Pretend it is upload now.
    self.repo_service.uploaded.add('a'*40)

    # Should register the package.
    resp = self.call_api('register_package', request)
    self.assertEqual(200, resp.status_code)
    self.assertEqual({
      'status': 'REGISTERED',
      'registered_by': 'user:mocked@example.com',
      'registered_ts': '1388534400000000',
    }, resp.json_body)

    # Check that it is indeed there.
    pkg = self.repo_service.get_instance('good/name', 'a'*40)
    self.assertTrue(pkg)
    expected = {
      'registered_by': auth.Identity(kind='user', name='mocked@example.com'),
      'registered_ts': datetime.datetime(2014, 1, 1, 0, 0),
      'signature_keys': ['sig key 1', 'sig key 2'],
      'signatures': [
        {
          'added_by': auth.Identity(kind='user', name='mocked@example.com'),
          'added_ts': datetime.datetime(2014, 1, 1, 0, 0),
          'digest': '\x00\x01\x02\x03\x04',
          'hash_algo': 'SHA1',
          'signature': 'signature \x00\x01\x02\x03\x04',
          'signature_algo': 'sig algo',
          'signature_key': 'sig key 1',
        },
        {
          'added_by': auth.Identity(kind='user', name='mocked@example.com'),
          'added_ts': datetime.datetime(2014, 1, 1, 0, 0),
          'digest': '\x00\x01\x02\x03\x04',
          'hash_algo': 'SHA1',
          'signature': 'signature \x00\x01\x02\x03\x04',
          'signature_algo': 'sig algo',
          'signature_key': 'sig key 2',
        },
      ],
    }
    self.assertEqual(expected, pkg.to_dict())

    # Attempt to register it again, with additional signature.
    request['signatures'].append({
      'hash_algo': 'SHA1',
      'digest': 'AAECAwQ=',
      'signature_algo': 'sig algo',
      'signature_key': 'sig key 3',
      'signature': 'c2lnbmF0dXJlIAABAgME',
    })
    resp = self.call_api('register_package', request)
    self.assertEqual(200, resp.status_code)
    self.assertEqual({
      'status': 'ALREADY_REGISTERED',
      'registered_by': 'user:mocked@example.com',
      'registered_ts': '1388534400000000',
    }, resp.json_body)

    # The signature is added to the list.
    pkg = self.repo_service.get_instance('good/name', 'a'*40)
    self.assertTrue(pkg)
    self.assertEqual(3, len(pkg.signatures))

  def test_register_package_bad_name(self):
    resp = self.call_api('register_package', {
      'package_name': 'bad name',
      'instance_id': 'a'*40,
    })
    self.assertEqual({
      'status': 'ERROR',
      'error_message': 'Invalid package name',
    }, resp.json_body)

  def test_register_package_bad_instance_id(self):
    resp = self.call_api('register_package', {
      'package_name': 'good/name',
      'instance_id': 'bad instance id',
    })
    self.assertEqual({
      'status': 'ERROR',
      'error_message': 'Invalid package instance ID',
    }, resp.json_body)

  def test_register_package_no_access(self):
    self.mock(api.acl, 'can_register_package', lambda *_: False)
    with self.call_should_fail(403):
      self.call_api('register_package', {
        'package_name': 'good/name',
        'instance_id': 'a'*40,
      })

  def test_register_package_no_service(self):
    self.repo_service = None
    with self.call_should_fail(500):
      self.call_api('register_package', {
        'package_name': 'good/name',
        'instance_id': 'a'*40,
      })


class MockedRepoService(impl.RepoService):
  """Almost like a real one, except CAS part is stubbed."""

  def __init__(self):
    super(MockedRepoService, self).__init__(None)
    self.uploaded = set()

  def is_instance_file_uploaded(self, package_name, instance_id):
    return instance_id in self.uploaded

  def create_upload_session(self, package_name, instance_id, caller):
    return 'http://upload_url', 'upload_session_id'
