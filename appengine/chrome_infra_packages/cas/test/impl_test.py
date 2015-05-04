# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# We need to keep same argument names for mocked calls (to accept kwargs), and
# thus can't use '_' prefix to silence the warming.
# pylint: disable=unused-argument

import datetime
import hashlib
import StringIO

from testing_utils import testing

from components import auth
from components import auth_testing
from components import utils

import cloudstorage
import config

from cas import impl
from . import common


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
    self.mock(config, 'cached', lambda: conf)
    self.assertIsNotNone(impl.get_cas_service())

  def test_get_cas_service_no_config(self):
    conf = config.GlobalConfig()
    self.mock(config, 'cached', lambda: conf)
    self.assertIsNone(impl.get_cas_service())

  def test_get_cas_service_bad_config(self):
    conf = config.GlobalConfig(
        cas_gs_path='blah',
        cas_gs_temp='/cas_gs_temp/def')
    self.mock(config, 'cached', lambda: conf)
    self.assertIsNone(impl.get_cas_service())

  def test_fetch(self):
    service = impl.CASService(
        '/bucket/real', '/bucket/temp',
        auth.ServiceAccountKey('account@email.com', 'PEM private key', 'id'))

    # Actual _rsa_sign implementation depends on PyCrypto, that for some reason
    # is not importable in unit tests. _rsa_sign is small enough to be "tested"
    # manually on the dev server.
    calls = []
    def fake_sign(pkey, data):
      calls.append((pkey, data))
      return '+signature+'
    self.mock(service, '_rsa_sign', fake_sign)
    self.mock_now(utils.timestamp_to_datetime(1416444987 * 1000000.))

    # Signature and email should be urlencoded.
    url = service.generate_fetch_url('SHA1', 'a' * 40)
    self.assertEqual(
        'https://storage.googleapis.com/bucket/real/SHA1/'
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa?'
        'GoogleAccessId=account%40email.com&'
        'Expires=1416448587&'
        'Signature=%2Bsignature%2B', url)

    # Since _rsa_sign is mocked out, at least verify it is called as expected.
    self.assertEqual([(
      'PEM private key',
      'GET\n\n\n1416448587\n/bucket/real/SHA1/' + 'a'*40
    )], calls)

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
      return common.Mock(
          _path_with_token='/bucket/temp/1416444987_1?upload_id=abc',
          _api=common.Mock(api_url='https://fake.com'))
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

    obj1 = common.make_fake_session(status=impl.UploadSession.STATUS_ERROR)
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

    obj1 = common.make_fake_session(status=impl.UploadSession.STATUS_UPLOADING)
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
    obj = common.make_fake_session(status=impl.UploadSession.STATUS_ERROR)
    obj.put()
    service = impl.CASService('/bucket/real', '/bucket/temp')
    self.assertTrue(service.verify_pending_upload(obj.key.id()))

  def test_verify_pending_upload_when_file_exists(self):
    obj = common.make_fake_session(
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
    obj = common.make_fake_session(
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

    obj = common.make_fake_session(
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

    obj = common.make_fake_session(
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
    self.mock(service, '_gs_copy', mocked_copy)

    self.assertTrue(service.verify_pending_upload(obj.key.id()))

    # Moved to PUBLISHED.
    obj = obj.key.get()
    self.assertEqual(obj.status, impl.UploadSession.STATUS_PUBLISHED)

  def test_open_ok(self):
    service = impl.CASService('/bucket/real', '/bucket/temp')
    calls = []
    def mocked_cloudstorage_open(**kwargs):
      calls.append(kwargs)
      return object()
    self.mock(impl.cloudstorage, 'open', mocked_cloudstorage_open)
    service.open('SHA1', 'a'*40, 1234)
    self.assertEqual(calls, [{
      'filename': '/bucket/real/SHA1/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      'mode': 'r',
      'read_buffer_size': 1234,
      'retry_params': service._retry_params,
    }])

  def test_open_not_found(self):
    service = impl.CASService('/bucket/real', '/bucket/temp')
    def mocked_cloudstorage_open(**kwargs):
      raise impl.cloudstorage.NotFoundError()
    self.mock(impl.cloudstorage, 'open', mocked_cloudstorage_open)
    with self.assertRaises(impl.NotFoundError):
      service.open('SHA1', 'a'*40, 1234)

  def test_direct_upload(self):
    service = impl.CASService('/bucket/real', '/bucket/temp')
    calls = []
    def mocked_cloudstorage_open(filename, **_kwargs):
      calls.append(('open', filename))
      return StringIO.StringIO()
    self.mock(impl.cloudstorage, 'open', mocked_cloudstorage_open)
    self.mock(service, '_gs_copy', lambda *a: calls.append(('copy',) + a))
    self.mock(service, '_gs_delete', lambda *a: calls.append(('delete',) + a))
    self.mock_now(datetime.datetime(2014, 1, 1))
    self.mock(impl.random, 'choice', lambda x: x[0])

    with service.start_direct_upload('SHA1') as f:
      f.write('abc')
      f.write('def')
    self.assertEqual(f.hash_digest, '1f8ac10f23c5b5bc1167bda84b833e5c057a77d2')
    self.assertEqual(f.length, 6)
    self.assertEqual([
      (
        'open',
        '/bucket/temp/1388534400_direct_aaaaaaaaaaaaaaaaaaaa',
      ),
      (
        'copy',
        '/bucket/temp/1388534400_direct_aaaaaaaaaaaaaaaaaaaa',
        '/bucket/real/SHA1/1f8ac10f23c5b5bc1167bda84b833e5c057a77d2',
      ),
      (
        'delete',
        '/bucket/temp/1388534400_direct_aaaaaaaaaaaaaaaaaaaa'
      ),
    ], calls)

    # Code coverage for second noop close.
    f.close()

    # Code coverage for commit=False code path.
    del calls[:]
    with self.assertRaises(ValueError):
      with service.start_direct_upload('SHA1') as f:
        f.write('abc')
        raise ValueError()
    self.assertEqual([
      (
        'open',
        '/bucket/temp/1388534400_direct_aaaaaaaaaaaaaaaaaaaa',
      ),
      (
        'delete',
        '/bucket/temp/1388534400_direct_aaaaaaaaaaaaaaaaaaaa'
      ),
    ], calls)
