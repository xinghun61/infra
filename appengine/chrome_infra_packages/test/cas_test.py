# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# We need to keep same argument names for mocked calls (to accept kwargs), and
# thus can't use '_' prefix to silence the warming.
# pylint: disable=unused-argument

import hashlib
import StringIO

# test_env should be loaded before any other app module.
from . import test_env

from testing_utils import testing

from components import auth_testing
from components import utils

import cas
import cloudstorage
import config

from cas import impl


################################################################################
# Endpoints API test.


class MockedCASService(object):  # pragma: no cover
  """Same interface as impl.CASService, but without implementation."""

  def is_object_present(self, hash_algo, hash_digest):
    return False

  def create_upload_session(self, hash_algo, hash_digest, caller):
    return make_fake_session(), 'signed_id'

  def fetch_upload_session(self, upload_session_id, caller):
    if upload_session_id == 'signed_id':
      return make_fake_session()
    return None

  def maybe_finish_upload(self, upload_session):
    if upload_session.status == impl.UploadSession.STATUS_UPLOADING:
      upload_session.status = impl.UploadSession.STATUS_VERIFYING
    return upload_session

  def verify_pending_upload(self, unsigned_upload_id):
    return True


def make_fake_session(uid=666L, **kwargs):
  defaults = dict(
      hash_algo='hashalgo',
      hash_digest='digest',
      temp_gs_location='/temp/location/666',
      final_gs_location='/final/location/abc',
      upload_url='https://example.com/upload_url?upload_id=somestuff',
      status=impl.UploadSession.STATUS_UPLOADING,
      created_by=auth_testing.DEFAULT_MOCKED_IDENTITY)
  defaults.update(kwargs)
  return impl.UploadSession(id=uid, **defaults)


class CASServiceApiTest(test_env.EndpointsApiTestCase):
  """Tests for API layer ONLY."""

  API_CLASS_NAME = 'CASServiceApi'

  def setUp(self):
    super(CASServiceApiTest, self).setUp()
    auth_testing.mock_get_current_identity(self)
    self.cas_service = MockedCASService()
    def mocked_get_cas_service():
      return self.cas_service
    self.mock(impl, 'get_cas_service', mocked_get_cas_service)

  def test_begin_upload_ok(self):
    resp = self.call_api('begin_upload', {
      'hash_algo': 'SHA1',
      'file_hash': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    })
    self.assertEqual(resp.json, {
      'status': 'SUCCESS',
      'upload_session_id': 'signed_id',
      'upload_url': 'https://example.com/upload_url?upload_id=somestuff',
    })

  def test_begin_upload_bad_algo(self):
    with self.should_fail(400):
      self.call_api('begin_upload', {
        'hash_algo': 'UBERHASH',
        'file_hash': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      })

  def test_begin_upload_bad_digest(self):
    with self.should_fail(400):
      self.call_api('begin_upload', {
        'hash_algo': 'SHA1',
        'file_hash': 'aaaa',
      })

  def test_begin_upload_no_service(self):
    self.cas_service = None
    with self.should_fail(500):
      self.call_api('begin_upload', {
        'hash_algo': 'SHA1',
        'file_hash': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      })

  def test_begin_upload_already_present(self):
    self.cas_service.is_object_present = lambda *_: True
    resp = self.call_api('begin_upload', {
      'hash_algo': 'SHA1',
      'file_hash': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    })
    self.assertEqual(resp.json, {
      'status': 'ALREADY_UPLOADED',
    })

  def test_finish_upload_ok(self):
    resp = self.call_api('finish_upload', {'upload_session_id': 'signed_id'})
    self.assertEqual(resp.json, {'status': 'VERIFYING'})

  def test_finish_upload_no_service(self):
    self.cas_service = None
    with self.should_fail(500):
      self.call_api('finish_upload', {'upload_session_id': 'signed_id'})

  def test_finish_upload_missing_upload(self):
    resp = self.call_api('finish_upload', {'upload_session_id': 'blah'})
    self.assertEqual(resp.json, {'status': 'MISSING'})

  def test_finish_upload_error(self):
    # Mock 'fetch_upload_session' to return errored session.
    errored_session = make_fake_session()
    errored_session.status = impl.UploadSession.STATUS_ERROR
    errored_session.error_message = 'Life is sad'
    self.cas_service.fetch_upload_session = lambda *_: errored_session
    resp = self.call_api('finish_upload', {'upload_session_id': 'signed_id'})
    self.assertEqual(resp.json, {
      'status': 'ERROR',
      'error_message': 'Life is sad',
    })


################################################################################
# Test for implementation (mocking GS calls).


class Mock(object):
  def __init__(self, **kwargs):
    for k, v in kwargs.iteritems():
      setattr(self, k, v)


class CASServiceImplTest(testing.AppengineTestCase):
  def setUp(self):
    super(CASServiceImplTest, self).setUp()
    self.mock_cloudstorage_stat([])
    self.mock_cloudstorage_delete()

  def mock_cloudstorage_stat(self, existing_files):
    existing_files = set(existing_files)
    def stat_mock(filename, retry_params):
      if filename in existing_files:
        return cloudstorage.GCSFileStat(filename, 0, 'etag', 0)
      raise cloudstorage.NotFoundError()
    self.mock(impl.cloudstorage, 'stat', stat_mock)

  def mock_cloudstorage_delete(self):
    deleted_set = set()
    def delete_mock(filename, retry_params):
      deleted_set.add(filename)
    self.mock(impl.cloudstorage, 'delete', delete_mock)
    return deleted_set

  def mock_now(self, now):
    super(CASServiceImplTest, self).mock_now(now)
    self.mock(utils, 'utcnow', lambda: now)

  def test_get_cas_service_ok(self):
    conf = config.GlobalConfig(
        cas_gs_path='/cas_gs_path/abc/',
        cas_gs_temp='/cas_gs_temp/def/')
    self.mock(config, 'config', lambda: conf)
    self.assertIsNotNone(impl.get_cas_service())

  def test_get_cas_service_no_config(self):
    conf = config.GlobalConfig()
    self.mock(config, 'config', lambda: conf)
    self.assertIsNone(impl.get_cas_service())

  def test_get_cas_service_bad_config(self):
    conf = config.GlobalConfig(
        cas_gs_path='blah',
        cas_gs_temp='/cas_gs_temp/def')
    self.mock(config, 'config', lambda: conf)
    self.assertIsNone(impl.get_cas_service())

  def test_is_object_present(self):
    service = impl.CASService('/bucket/real', '/bucket/temp')
    self.mock_cloudstorage_stat(['/bucket/real/SHA1/' + 'a' * 40])
    self.assertTrue(service.is_object_present('SHA1', 'a' * 40))
    self.assertFalse(service.is_object_present('SHA1', 'b' * 40))
    with self.assertRaises(AssertionError):
      service.is_object_present('SHA1', 'wrong')

  def test_create_upload_session_and_fetch_upload_session(self):
    service = impl.CASService('/bucket/real', '/bucket/temp')

    mocked_time = utils.timestamp_to_datetime(1416444987 * 1000000.)
    self.mock_now(mocked_time)

    def mocked_open(filename, mode, retry_params):
      self.assertEqual(filename, '/bucket/temp/1416444987_1')
      self.assertEqual(mode, 'w')
      self.assertEqual(retry_params, service._retry_params)
      # Mock guts of ReadingBuffer :(
      return Mock(
          _path_with_token='/bucket/temp/1416444987_1?upload_id=abc',
          _api=Mock(api_url='https://fake.com'))
    self.mock(impl.cloudstorage, 'open', mocked_open)

    obj, signed_id = service.create_upload_session(
        'SHA1', 'a' * 40, auth_testing.DEFAULT_MOCKED_IDENTITY)
    self.assertEqual(obj.key.id(), 1)
    self.assertEqual(obj.to_dict(), {
      'created_by': auth_testing.DEFAULT_MOCKED_IDENTITY,
      'created_ts': mocked_time,
      'error_message': None,
      'final_gs_location': '/bucket/real/SHA1/' + 'a' * 40,
      'hash_algo': 'SHA1',
      'hash_digest': 'a' * 40,
      'status': impl.UploadSession.STATUS_UPLOADING,
      'temp_gs_location': '/bucket/temp/1416444987_1',
      'upload_url': 'https://fake.com/bucket/temp/1416444987_1?upload_id=abc',
    })

    # Token should be readable.
    embedded = impl.UploadIdSignature.validate(
        signed_id, [auth_testing.DEFAULT_MOCKED_IDENTITY.to_bytes()])
    self.assertEqual(embedded, {'id': '1'})

    # Verify fetch_upload_session can use it too.
    fetched = service.fetch_upload_session(
        signed_id, auth_testing.DEFAULT_MOCKED_IDENTITY)
    self.assertIsNotNone(fetched)
    self.assertEqual(fetched.to_dict(), obj.to_dict())

  def test_fetch_upload_session_bad_token(self):
    service = impl.CASService('/bucket/real', '/bucket/temp')
    obj = service.fetch_upload_session(
        'blah', auth_testing.DEFAULT_MOCKED_IDENTITY)
    self.assertIsNone(obj)

  def test_maybe_finish_upload_non_uploading(self):
    service = impl.CASService('/bucket/real', '/bucket/temp')

    def die(**_kwargs):  # pragma: no cover
      self.fail('Should not be called')
    self.mock(impl.utils, 'enqueue_task', die)

    obj1 = make_fake_session(status=impl.UploadSession.STATUS_ERROR)
    obj1.put()

    # Left in the same state.
    obj2 = service.maybe_finish_upload(obj1)
    self.assertEqual(obj2.status, impl.UploadSession.STATUS_ERROR)

  def test_maybe_finish_upload(self):
    service = impl.CASService('/bucket/real', '/bucket/temp')

    calls = []
    def mocked_enqueue_task(**kwargs):
      calls.append(kwargs)
      return True
    self.mock(impl.utils, 'enqueue_task', mocked_enqueue_task)

    obj1 = make_fake_session(status=impl.UploadSession.STATUS_UPLOADING)
    obj1.put()

    # Changed state.
    obj2 = service.maybe_finish_upload(obj1)
    self.assertEqual(obj2.status, impl.UploadSession.STATUS_VERIFYING)

    # Task enqueued.
    self.assertEqual(calls, [{
      'queue_name': 'cas-verify',
      'transactional': True,
      'url': '/internal/taskqueue/cas-verify/666',
    }])

  def test_verify_pending_upload_bad_session(self):
    service = impl.CASService('/bucket/real', '/bucket/temp')
    self.assertTrue(service.verify_pending_upload(1234))

  def test_verify_pending_upload_bad_state(self):
    obj = make_fake_session(status=impl.UploadSession.STATUS_ERROR)
    obj.put()
    service = impl.CASService('/bucket/real', '/bucket/temp')
    self.assertTrue(service.verify_pending_upload(obj.key.id()))

  def test_verify_pending_upload_when_file_exists(self):
    obj = make_fake_session(
        status=impl.UploadSession.STATUS_VERIFYING,
        final_gs_location='/bucket/real/SHA1/' + 'a' * 40,
        temp_gs_location='/bucket/temp/temp_crap')
    obj.put()

    self.mock_cloudstorage_stat([obj.final_gs_location])
    deleted_files = self.mock_cloudstorage_delete()

    service = impl.CASService('/bucket/real', '/bucket/temp')
    self.assertTrue(service.verify_pending_upload(obj.key.id()))

    # Moved to PUBLISHED.
    obj = obj.key.get()
    self.assertEqual(obj.status, impl.UploadSession.STATUS_PUBLISHED)

    # Temp clean up called.
    self.assertEqual(deleted_files, set(['/bucket/temp/temp_crap']))

  def test_verify_pending_upload_unfinalized(self):
    obj = make_fake_session(
        status=impl.UploadSession.STATUS_VERIFYING,
        final_gs_location='/bucket/real/SHA1/' + 'a' * 40,
        temp_gs_location='/bucket/temp/temp_crap')
    obj.put()

    def mocked_open(filename, mode, read_buffer_size, retry_params):
      self.assertEqual(filename, '/bucket/temp/temp_crap')
      self.assertEqual(mode, 'r')
      self.assertEqual(read_buffer_size, impl.READ_BUFFER_SIZE)
      raise cloudstorage.NotFoundError()
    self.mock(impl.cloudstorage, 'open', mocked_open)

    service = impl.CASService('/bucket/real', '/bucket/temp')
    self.assertTrue(service.verify_pending_upload(obj.key.id()))

    # Moved to ERROR.
    obj = obj.key.get()
    self.assertEqual(obj.status, impl.UploadSession.STATUS_ERROR)
    self.assertEqual(
        obj.error_message, 'Google Storage upload wasn\'t finalized.')

  def test_verify_pending_upload_bad_hash(self):
    fake_file = StringIO.StringIO('test buffer')
    fake_file._etag = 'fake_etag'

    obj = make_fake_session(
        status=impl.UploadSession.STATUS_VERIFYING,
        hash_algo='SHA1',
        hash_digest='a' * 40,
        final_gs_location='/bucket/real/SHA1/' + 'a' * 40,
        temp_gs_location='/bucket/temp/temp_crap')
    obj.put()

    def mocked_open(filename, mode, read_buffer_size, retry_params):
      self.assertEqual(filename, '/bucket/temp/temp_crap')
      self.assertEqual(mode, 'r')
      self.assertEqual(read_buffer_size, impl.READ_BUFFER_SIZE)
      return fake_file
    self.mock(impl.cloudstorage, 'open', mocked_open)

    service = impl.CASService('/bucket/real', '/bucket/temp')
    self.assertTrue(service.verify_pending_upload(obj.key.id()))

    # Moved to ERROR.
    obj = obj.key.get()
    self.assertEqual(obj.status, impl.UploadSession.STATUS_ERROR)
    self.assertEqual(
        obj.error_message,
        'Invalid SHA1 hash: expected aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, '
        'got 9682248358c830bcb5f8cb867186022acfe6eeb3.')

  def test_verify_pending_upload_good_hash(self):
    fake_file = StringIO.StringIO('test buffer')
    fake_file._etag = 'fake_etag'

    obj = make_fake_session(
        status=impl.UploadSession.STATUS_VERIFYING,
        hash_algo='SHA1',
        hash_digest='9682248358c830bcb5f8cb867186022acfe6eeb3',
        final_gs_location=(
            '/bucket/real/SHA1/9682248358c830bcb5f8cb867186022acfe6eeb3'),
        temp_gs_location='/bucket/temp/temp_crap')
    obj.put()

    def mocked_open(filename, mode, read_buffer_size, retry_params):
      self.assertEqual(filename, '/bucket/temp/temp_crap')
      self.assertEqual(mode, 'r')
      self.assertEqual(read_buffer_size, impl.READ_BUFFER_SIZE)
      return fake_file
    self.mock(impl.cloudstorage, 'open', mocked_open)

    service = impl.CASService('/bucket/real', '/bucket/temp')

    def mocked_copy(src, dst, src_etag):
      self.assertEqual(src, '/bucket/temp/temp_crap')
      self.assertEqual(
          dst, '/bucket/real/SHA1/9682248358c830bcb5f8cb867186022acfe6eeb3')
      self.assertEqual(src_etag, 'fake_etag')
    self.mock(service, '_gs_copy_if_source_matches', mocked_copy)

    self.assertTrue(service.verify_pending_upload(obj.key.id()))

    # Moved to PUBLISHED.
    obj = obj.key.get()
    self.assertEqual(obj.status, impl.UploadSession.STATUS_PUBLISHED)
