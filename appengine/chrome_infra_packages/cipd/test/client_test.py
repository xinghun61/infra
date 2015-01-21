# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import StringIO

from testing_support import auto_stub

from cas import impl as cas_impl

from cipd import client
from cipd import processing
from cipd import reader


class ClientUtilsTest(auto_stub.TestCase):
  def test_is_cipd_client_package(self):
    call = client.is_cipd_client_package
    self.assertTrue(call('infra/tools/cipd/linux-amd64'))
    self.assertTrue(call('infra/tools/cipd/mac-amd64-osx10.8'))
    self.assertTrue(call('infra/tools/cipd/windows-amd64'))
    self.assertFalse(call('infra/tools/cipd/huh-amd64'))
    self.assertFalse(call('infra/stuff'))

  def test_get_cipd_client_filename(self):
    self.assertEqual(
        'cipd',
        client.get_cipd_client_filename('infra/tools/cipd/linux-amd64'))
    self.assertEqual(
        'cipd',
        client.get_cipd_client_filename('infra/tools/cipd/mac-amd64-osx-10.8'))
    self.assertEqual(
        'cipd.exe',
        client.get_cipd_client_filename('infra/tools/cipd/windows-amd64'))
    with self.assertRaises(ValueError):
      client.get_cipd_client_filename('some/other/package')

  def test_extract_cipd_client_processor_ok(self):
    proc = client.ExtractCIPDClientProcessor(FakeCASService())
    result = proc.run(FakeInstance(), FakePackageReader('some data'))
    self.assertEqual({
      'client_binary': {
        'hash_algo': 'SHA1',
        'hash_digest': 'baf34551fecb48acc3da868eb85e1b6dac9de356',
        'size': 9,
      },
    }, result)

  def test_extract_cipd_client_processor_error(self):
    proc = client.ExtractCIPDClientProcessor(FakeCASService())
    with self.assertRaises(processing.ProcessingError):
      proc.run(FakeInstance(), FakePackageReader(None))


class FakeInstance(object):
  package_name = 'infra/tools/cipd/linux-amd64'
  instance_id = 'a'*40


class FakePackageReader(object):
  def __init__(self, data):
    self.data = data

  def open_packaged_file(self, path):
    assert path == 'cipd'
    if self.data is None:
      raise reader.NoSuchPackagedFileError()
    return StringIO.StringIO(self.data)


class FakeCASService(object):
  def start_direct_upload(self, hash_algo):
    assert hash_algo == 'SHA1'
    return cas_impl.DirectUpload(
        file_obj=StringIO.StringIO(),
        hasher=hashlib.sha1(),
        callback=lambda *_args: None)
