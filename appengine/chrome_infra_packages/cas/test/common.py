# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities used from *_test.py."""

# We need to keep same argument names for mocked calls (to accept kwargs), and
# thus can't use '_' prefix to silence the warming.
# pylint: disable=unused-argument

from components import auth_testing
from cas import impl


class MockedCASService(object):  # pragma: no cover
  """Same interface as impl.CASService, but without implementation."""

  def is_fetch_configured(self):
    return True

  def is_object_present(self, hash_algo, hash_digest):
    return False

  def generate_fetch_url(self, hash_algo, hash_digest):
    return 'https://signed-url.example.com/%s/%s' % (hash_algo, hash_digest)

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


def make_fake_session(uid=666L, **kwargs):  # pragma: no cover
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


class Mock(object):  # pragma: no cover
  def __init__(self, **kwargs):
    for k, v in kwargs.iteritems():
      setattr(self, k, v)
