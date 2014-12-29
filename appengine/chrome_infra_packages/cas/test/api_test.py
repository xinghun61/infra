# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing
from components import auth_testing

from cas import api
from cas import impl

from . import common


class CASServiceApiTest(testing.EndpointsTestCase):
  """Tests for API layer ONLY."""

  api_service_cls = api.CASServiceApi

  def setUp(self):
    super(CASServiceApiTest, self).setUp()
    auth_testing.mock_get_current_identity(self)
    self.cas_service = common.MockedCASService()
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
    with self.call_should_fail(400):
      self.call_api('begin_upload', {
        'hash_algo': 'UBERHASH',
        'file_hash': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      })

  def test_begin_upload_bad_digest(self):
    with self.call_should_fail(400):
      self.call_api('begin_upload', {
        'hash_algo': 'SHA1',
        'file_hash': 'aaaa',
      })

  def test_begin_upload_no_service(self):
    self.cas_service = None
    with self.call_should_fail(500):
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
    with self.call_should_fail(500):
      self.call_api('finish_upload', {'upload_session_id': 'signed_id'})

  def test_finish_upload_missing_upload(self):
    resp = self.call_api('finish_upload', {'upload_session_id': 'blah'})
    self.assertEqual(resp.json, {'status': 'MISSING'})

  def test_finish_upload_error(self):
    # Mock 'fetch_upload_session' to return errored session.
    errored_session = common.make_fake_session()
    errored_session.status = impl.UploadSession.STATUS_ERROR
    errored_session.error_message = 'Life is sad'
    self.cas_service.fetch_upload_session = lambda *_: errored_session
    resp = self.call_api('finish_upload', {'upload_session_id': 'signed_id'})
    self.assertEqual(resp.json, {
      'status': 'ERROR',
      'error_message': 'Life is sad',
    })
