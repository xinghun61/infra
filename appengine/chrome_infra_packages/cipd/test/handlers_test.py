# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=unused-argument

from testing_utils import testing

from components import auth

from cipd import acl
from cipd import handlers
from cipd import impl


class Interrupt(Exception):
  def __init__(self, code, data):
    super(Interrupt, self).__init__()
    self.code = code
    self.data = data


class MockedRepoService(object):
  def __init__(self):
    self.client_bin_err = None
    self.no_client_bin = False

  def resolve_version(self, pkg, version, limit):
    if pkg == 'infra/tools/cipd/mac-amd64' and version == 'ref':
      return ['a'*40]
    if version == 'tag:1':
      return ['a'*40, 'b'*40]
    return None

  def get_instance(self, pkg, iid):
    if pkg == 'infra/tools/cipd/mac-amd64' and iid == 'a'*40:
      return impl.PackageInstance(key=impl.package_instance_key(pkg, iid))
    return None

  def get_client_binary_info(self, instance, filename=None):
    if self.client_bin_err:
      return None, self.client_bin_err
    if self.no_client_bin:
      return None, None
    return impl.ClientBinaryInfo(
        sha1='...', size=1000, fetch_url='http://fetch_url/%s' % filename), None


class ClientHandlerTest(testing.AppengineTestCase):

  def setUp(self):
    super(ClientHandlerTest, self).setUp()
    self.repo_mock = MockedRepoService()
    self.mock(auth, 'get_current_identity', lambda: auth.Anonymous)
    self.mock(acl, 'can_fetch_instance', lambda *_args: True)
    self.mock(impl, 'get_repo_service', lambda: self.repo_mock)

  def call(self, platform, version):
    h = handlers.ClientHandler()
    h.request = {'platform': platform, 'version': version}

    def mocked_abort(code, details):
      raise Interrupt(code, details)
    self.mock(h, 'abort', mocked_abort)
    def mocked_redirect(url):
      raise Interrupt(302, url)
    self.mock(h, 'redirect', mocked_redirect)

    try:
      h.get()
    except Interrupt as exc:
      return exc.code, exc.data
    else:  # pragma: no cover
      self.fail('The request didn\'t complete')

  def test_happy_path_with_ref(self):
    self.assertEqual(
        self.call('mac-amd64', 'ref'), (302, 'http://fetch_url/cipd'))

  def test_happy_path_with_sha1(self):
    self.assertEqual(
        self.call('mac-amd64', 'a'*40), (302, 'http://fetch_url/cipd'))

  def test_no_platform(self):
    self.assertEqual(
        self.call(None, 'version'), (400, 'No "platform" specified.'))

  def test_no_version(self):
    self.assertEqual(
        self.call('platform', None), (400, 'No "version" specified.'))

  def test_invalid_platform(self):
    self.assertEqual(
        self.call('@@@@', 'version'), (400, 'Invalid platform name.'))

  def test_unknown_platform(self):
    self.assertEqual(
        self.call('solaris', 'version'), (400, 'Unrecognized platform name.'))

  def test_invalid_version(self):
    self.assertEqual(
        self.call('mac-amd64', '@@@@@'), (400, 'Invalid version identifier.'))

  def test_not_allowed(self):
    self.mock(acl, 'can_fetch_instance', lambda *_args: False)
    self.assertEqual(
        self.call('mac-amd64', 'ref'), (403, 'Not allowed.'))

  def test_repo_not_configured(self):
    self.repo_mock = None
    self.assertEqual(
        self.call('mac-amd64', 'ref'), (500, 'The service is not configured.'))

  def test_unknown_version(self):
    self.assertEqual(
        self.call('mac-amd64', 'zzz'), (404, 'No such package.'))

  def test_ambigious_version(self):
    self.assertEqual(
        self.call('mac-amd64', 'tag:1'),
        (
          409,
          'The provided tag points to multiple instances, can\'t use it '
          'as a version identifier.'
        ))

  def test_nonexisting_id(self):
    self.assertEqual(
        self.call('mac-amd64', 'c'*40), (404, 'No such package.'))

  def test_extraction_error(self):
    self.repo_mock.client_bin_err = 'blah'
    self.assertEqual(
        self.call('mac-amd64', 'ref'),
        (404, 'The client binary is not available. Error: blah.'))

  def test_still_extracting(self):
    self.repo_mock.no_client_bin = True
    self.assertEqual(
        self.call('mac-amd64', 'ref'),
        (404, 'The client binary is not extracted yet, try later.'))
