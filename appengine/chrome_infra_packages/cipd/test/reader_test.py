# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import StringIO
import zipfile

from testing_support import auto_stub

from cipd import reader


class ReaderTest(auto_stub.TestCase):
  def test_works(self):
    zipped_data = self.zip_data([
      ('dir/data', 'some data'),
      ('dir/file', '123456'),
      ('file', 'blah-blah-blah'),
    ])
    cas_service = self.fake_cas_service(zipped_data)
    with reader.PackageReader(cas_service, 'SHA1', 'a'*40) as r:
      # File listing.
      files = r.get_packaged_files()
      self.assertEqual((
        reader.PackagedFileInfo('dir/data', 9),
        reader.PackagedFileInfo('dir/file', 6),
        reader.PackagedFileInfo('file', 14),
      ), files)
      # Open existing file.
      with r.open_packaged_file('dir/data') as f:
        data = f.read()
      self.assertEqual('some data', data)
      # Open missing file.
      with self.assertRaises(reader.NoSuchPackagedFileError):
        r.open_packaged_file('missing_file')

  def test_bad_zip_file(self):
    cas_service = self.fake_cas_service('im not a zip file, at all')
    with reader.PackageReader(cas_service, 'SHA1', 'a'*40) as r:
      with self.assertRaises(reader.BadPackageError):
        r.get_packaged_files()

  def test_missing(self):
    cas_service = self.fake_cas_service(None)
    with reader.PackageReader(cas_service, 'SHA1', 'a'*40) as r:
      with self.assertRaises(reader.BadPackageError):
        r.get_packaged_files()

  def test_corrupted_zip_file(self):
    zipped_data = self.zip_data([('file', 'blah-blah-blah')])
    zipped_data = zipped_data[:5] + zipped_data[7:]
    cas_service = self.fake_cas_service(zipped_data)
    with reader.PackageReader(cas_service, 'SHA1', 'a'*40) as r:
      with self.assertRaises(reader.BadPackageError):
        r.open_packaged_file('file')

  def fake_cas_service(self, zipped_data):
    test = self
    class FakeCASService(object):
      def open(self, hash_algo, hash_digest, read_buffer_size):
        test.assertEqual('SHA1', hash_algo)
        test.assertEqual('a'*40, hash_digest)
        test.assertTrue(read_buffer_size)
        if zipped_data is None:
          raise reader.cas.NotFoundError()
        return StringIO.StringIO(zipped_data)
    return FakeCASService()

  @staticmethod
  def zip_data(items):
    out = StringIO.StringIO()
    zf = zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED)
    for path, data in items:
      zf.writestr(path, data)
    zf.close()
    return out.getvalue()
