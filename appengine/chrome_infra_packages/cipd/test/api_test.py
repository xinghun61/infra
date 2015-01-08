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


class PackageRepositoryApiTest(testing.EndpointsTestCase):
  """Tests for API layer ONLY."""

  api_service_cls = api.PackageRepositoryApi

  def setUp(self):
    super(PackageRepositoryApiTest, self).setUp()
    auth_testing.mock_get_current_identity(self)
    auth_testing.mock_is_admin(self)
    self.repo_service = MockedRepoService()
    self.mock(impl, 'get_repo_service', lambda: self.repo_service)

  def test_fetch_instance_ok(self):
    _, registered = self.repo_service.register_instance(
        package_name='good/name',
        instance_id='a'*40,
        caller=auth.Identity.from_bytes('user:abc@example.com'),
        now=datetime.datetime(2014, 1, 1))
    self.assertTrue(registered)

    resp = self.call_api('fetch_instance', {
      'package_name': 'good/name',
      'instance_id': 'a'*40,
    })
    self.assertEqual({
      'fetch_url': 'http://signed-url/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      'instance': {
        'instance_id': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        'package_name': 'good/name',
        'registered_by': 'user:abc@example.com',
        'registered_ts': '1388534400000000',
      },
      'status': 'SUCCESS',
    }, resp.json_body)

  def test_fetch_instance_no_access(self):
    _, registered = self.repo_service.register_instance(
        package_name='good/name',
        instance_id='a'*40,
        caller=auth.Identity.from_bytes('user:abc@example.com'),
        now=datetime.datetime(2014, 1, 1))
    self.assertTrue(registered)

    # Should return PACKAGE_NOT_FOUND even though package exists.
    self.mock(api.acl, 'can_fetch_instance', lambda *_: False)
    resp = self.call_api('fetch_instance', {
      'package_name': 'good/name',
      'instance_id': 'a'*40,
    })
    self.assertEqual({'status': 'PACKAGE_NOT_FOUND'}, resp.json_body)

  def test_fetch_instance_no_such_package(self):
    resp = self.call_api('fetch_instance', {
      'package_name': 'good/name',
      'instance_id': 'a'*40,
    })
    self.assertEqual({'status': 'PACKAGE_NOT_FOUND'}, resp.json_body)

  def test_fetch_instance_no_such_instance(self):
    _, registered = self.repo_service.register_instance(
        package_name='good/name',
        instance_id='a'*40,
        caller=auth.Identity.from_bytes('user:abc@example.com'),
        now=datetime.datetime(2014, 1, 1))
    self.assertTrue(registered)

    resp = self.call_api('fetch_instance', {
      'package_name': 'good/name',
      'instance_id': 'b'*40,
    })
    self.assertEqual({'status': 'INSTANCE_NOT_FOUND'}, resp.json_body)

  def test_fetch_instance_bad_name(self):
    resp = self.call_api('fetch_instance', {
      'package_name': 'bad name',
      'instance_id': 'a'*40,
    })
    self.assertEqual({
      'status': 'ERROR',
      'error_message': 'Invalid package name',
    }, resp.json_body)

  def test_fetch_instance_bad_instance_id(self):
    resp = self.call_api('fetch_instance', {
      'package_name': 'good/name',
      'instance_id': 'bad instance id',
    })
    self.assertEqual({
      'status': 'ERROR',
      'error_message': 'Invalid package instance ID',
    }, resp.json_body)

  def test_fetch_instance_no_service(self):
    self.repo_service = None
    with self.call_should_fail(500):
      self.call_api('fetch_instance', {
        'package_name': 'good/name',
        'instance_id': 'a'*40,
      })

  def test_register_new_instance_flow(self):
    self.mock(utils, 'utcnow', lambda: datetime.datetime(2014, 1, 1))
    request = {
      'package_name': 'good/name',
      'instance_id': 'a'*40,
    }

    # Package is not uploaded yet. Should ask to upload.
    resp = self.call_api('register_instance', request)
    self.assertEqual(200, resp.status_code)
    self.assertEqual({
      'status': 'UPLOAD_FIRST',
      'upload_session_id': 'upload_session_id',
      'upload_url': 'http://upload_url',
    }, resp.json_body)

    # Pretend it is upload now.
    self.repo_service.uploaded.add('a'*40)

    # Should register the package.
    resp = self.call_api('register_instance', request)
    self.assertEqual(200, resp.status_code)
    self.assertEqual({
      'status': 'REGISTERED',
      'instance': {
        'instance_id': 'a'*40,
        'package_name': 'good/name',
        'registered_by': 'user:mocked@example.com',
        'registered_ts': '1388534400000000',
      },
    }, resp.json_body)

    # Check that it is indeed there.
    pkg = self.repo_service.get_instance('good/name', 'a'*40)
    self.assertTrue(pkg)
    expected = {
      'registered_by': auth.Identity(kind='user', name='mocked@example.com'),
      'registered_ts': datetime.datetime(2014, 1, 1, 0, 0),
    }
    self.assertEqual(expected, pkg.to_dict())

    # Attempt to register it again.
    resp = self.call_api('register_instance', request)
    self.assertEqual(200, resp.status_code)
    self.assertEqual({
      'status': 'ALREADY_REGISTERED',
      'instance': {
        'instance_id': 'a'*40,
        'package_name': 'good/name',
        'registered_by': 'user:mocked@example.com',
        'registered_ts': '1388534400000000',
      },
    }, resp.json_body)

  def test_register_instance_bad_name(self):
    resp = self.call_api('register_instance', {
      'package_name': 'bad name',
      'instance_id': 'a'*40,
    })
    self.assertEqual({
      'status': 'ERROR',
      'error_message': 'Invalid package name',
    }, resp.json_body)

  def test_register_instance_bad_instance_id(self):
    resp = self.call_api('register_instance', {
      'package_name': 'good/name',
      'instance_id': 'bad instance id',
    })
    self.assertEqual({
      'status': 'ERROR',
      'error_message': 'Invalid package instance ID',
    }, resp.json_body)

  def test_register_instance_no_access(self):
    self.mock(api.acl, 'can_register_instance', lambda *_: False)
    with self.call_should_fail(403):
      self.call_api('register_instance', {
        'package_name': 'good/name',
        'instance_id': 'a'*40,
      })

  def test_register_instance_no_service(self):
    self.repo_service = None
    with self.call_should_fail(500):
      self.call_api('register_instance', {
        'package_name': 'good/name',
        'instance_id': 'a'*40,
      })


class MockedRepoService(impl.RepoService):
  """Almost like a real one, except CAS part is stubbed."""

  def __init__(self):
    super(MockedRepoService, self).__init__(None)
    self.uploaded = set()

  def is_fetch_configured(self):
    return True

  def generate_fetch_url(self, instance):
    return 'http://signed-url/%s' % instance.instance_id

  def is_instance_file_uploaded(self, package_name, instance_id):
    return instance_id in self.uploaded

  def create_upload_session(self, package_name, instance_id, caller):
    return 'http://upload_url', 'upload_session_id'
