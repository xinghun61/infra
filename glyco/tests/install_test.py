# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys
import unittest

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'third_party'))

from glucose import install
from glucose import main_
from glucose import pack
from glucose import util


class ParserTest(unittest.TestCase):
  def test_install_zero_packages(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['install'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

  def test_install_one_package(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['install', 'package_name.whl',
                                 '-i', 'nice-dir'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

  def test_install_two_packages(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['install', 'package_name.whl',
                                 'package2_name.whl', '-i', 'nice-dir2'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))


class CheckSha1Test(unittest.TestCase):
  def test_good_hash(self):
    filename = os.path.join(
      DATA_DIR, 'wheels', 'source_package_valid_sha1-0.0.1-0_'
      + '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
    self.assertTrue(install.has_valid_sha1(filename, verbose=False))

  def test_bad_hash(self):
    filename = os.path.join(
      DATA_DIR, 'wheels', 'source_package_invalid_sha1-0.0.1-0_'
      + 'deadbeef3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
    self.assertFalse(install.has_valid_sha1(filename, verbose=False))

  def test_no_build_number(self):
    # The file doesn't have to exist.
    filename = ('source_package_invalid_sha1-0.0.1-py2-none-any.whl')
    self.assertFalse(install.has_valid_sha1(filename, verbose=False))

  def test_invalid_filename(self):
    # The file doesn't have to exist.
    filename = ('source_package.txt')
    self.assertFalse(install.has_valid_sha1(filename, verbose=False))


class InstallLocalPackagesTest(unittest.TestCase):
  def test_install_one_package(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)

    with util.temporary_directory(prefix='glyco-install-test-') as tempdir:
      options = parser.parse_args(['pack',
                                   os.path.join(DATA_DIR, 'source_package'),
                                   '--output-dir', tempdir])
      self.assertFalse(pack.pack(options))
      wheel_paths = [os.path.join(tempdir, whl) for whl in os.listdir(tempdir)]

      options = parser.parse_args(
        ['install', wheel_paths[0],
         '--install-dir', os.path.join(tempdir, 'local')])

      install.install(options)
      self.assertTrue(os.path.isdir(
        os.path.join(tempdir, 'local', 'source_package')))
      self.assertTrue(
        len(os.listdir(os.path.join(tempdir, 'local', 'source_package'))) > 0)
      self.assertTrue(os.path.isdir(
          os.path.join(tempdir, 'local', 'source_package-0.0.1.dist-info')))

  def test_install_two_packages(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)

    with util.temporary_directory(prefix='glyco-install-test-') as tempdir:
      options = parser.parse_args(['pack',
                                   os.path.join(DATA_DIR, 'source_package'),
                                   os.path.join(DATA_DIR, 'installed_package'),
                                   '--output-dir', tempdir])
      self.assertFalse(pack.pack(options))
      wheel_paths = [os.path.join(tempdir, whl) for whl in os.listdir(tempdir)]

      options = parser.parse_args(
        ['install', wheel_paths[0], wheel_paths[1],
         '--install-dir', os.path.join(tempdir, 'local')])

      install.install(options)
      self.assertTrue(os.path.isdir(
        os.path.join(tempdir, 'local', 'source_package')))
      # Make sure the directory is not empty.
      self.assertTrue(
        len(os.listdir(os.path.join(tempdir, 'local', 'source_package'))) > 0)
      self.assertTrue(os.path.isdir(
          os.path.join(tempdir, 'local', 'source_package-0.0.1.dist-info')))

      self.assertTrue(os.path.isdir(
        os.path.join(tempdir, 'local', 'installed_package')))
      self.assertTrue(
        len(os.listdir(
          os.path.join(tempdir, 'local', 'installed_package'))) > 0)
      self.assertTrue(os.path.isdir(
          os.path.join(tempdir, 'local', 'installed_package-0.0.1.dist-info')))

  def test_install_invalid_hash(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    with util.temporary_directory(prefix='glyco-install-test-') as tempdir:
      options = parser.parse_args([
        'install', os.path.join(
            DATA_DIR, 'wheels', 'source_package_invalid_sha1-0.0.1-0_'
            + 'deadbeef3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl'),
        '--install-dir', os.path.join(tempdir, 'local')])

      result = install.install(options)

    self.assertNotEqual(result, 0)


class FakeHttp(object):
  """Replacement object for httplib2.Http"""

  def __init__(self):
    # Map url to header and filename containing response.
    # File names are relative to DATA_DIR
    self.filenames = {}
    filenames = self.filenames  # saving a few characters.

    # Good file
    filenames['https://a.random.host.com/'
              'source_package_valid_sha1-0.0.1-0_'
              '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl'] = [
      {'status': '200'},
      os.path.join('wheels',
                   'source_package_valid_sha1-0.0.1-0_'
                   '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
              ]

    # Bad files
    filenames['https://a.random.host.com/'
              'source_package_invalid_sha1-0.0.1-0_'
              'deadbeef3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl'] = [
      {'status': '200'},
      os.path.join('wheels',
                   'source_package_invalid_sha1-0.0.1-0_'
                   'deadbeef3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
              ]

    filenames['https://a.random.host.com/invalid_name.whl'] = [
      {'status': '200'},
      os.path.join('wheels',
                   'source_package_invalid_sha1-0.0.1-0_'
                   'deadbeef3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
              ]

    # And simulating an error.
    filenames['https://a.broken.host.com/'
              'source_package_valid_sha1-0.0.1-0_'
              '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl'] = [
      {'status': '403'}, None
    ]

  def request(self, url, verb):
    if verb != 'GET':
      raise NotImplementedError('Only GET is implementd in this mock.')
    resp, filename = self.filenames[url]
    content = ''
    if filename:
      with open(os.path.join(DATA_DIR, filename), 'rb') as f:
        content = f.read()
    return resp, content


class FetchPackagesTest(unittest.TestCase):
  def test_fetch_one_file(self):
    requester = None
    with util.temporary_directory(prefix='glyco-fetch-test-') as tempdir:
      cache = os.path.join(tempdir, 'cache')
      location = os.path.join(
        DATA_DIR,
        'wheels',
        'source_package_valid_sha1-0.0.1-0_'
        '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')

      install_list = [{'location': 'file://' + location,
                       'location_type': 'file'}]
      paths = install.fetch_packages(
        install_list, requester=requester, cache=cache, verbose=False)

      self.assertEqual(len(paths), 1)
      self.assertEqual(paths[0], location)
      # The file is readily available, nothing should be copied to the cache.
      self.assertEqual(len(os.listdir(cache)), 0)

  def test_fetch_two_files(self):
    requester = None
    with util.temporary_directory(prefix='glyco-fetch-test-') as tempdir:
      cache = os.path.join(tempdir, 'cache')
      locations = [
        os.path.join(
          DATA_DIR,
          'wheels',
          'source_package_valid_sha1-0.0.1-0_'
          '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl'
        ),
        os.path.join(
          DATA_DIR,
          'wheels',
          'installed_package-0.0.1-0_'
          '58a752f45f35a07c7d94149511b3af04bab11740-py2-none-any.whl'
        )
      ]

      install_list = [{'location': 'file://' + location,
                       'location_type': 'file'}
                      for location in locations]
      paths = install.fetch_packages(
        install_list, requester=requester, cache=cache, verbose=False)

      self.assertEqual(len(paths), 2)
      self.assertEqual(paths[0], locations[0])
      self.assertEqual(paths[1], locations[1])

      # The file is readily available, nothing should be copied to the cache.
      self.assertEqual(len(os.listdir(cache)), 0)

  def test_fetch_one_invalid_file(self):
    requester = None
    with util.temporary_directory(prefix='glyco-fetch-test-') as tempdir:
      cache = os.path.join(tempdir, 'cache')
      location = os.path.join(
        DATA_DIR,
        'wheels',
        'source_package_invalid_sha1-0.0.1-0_'
        'deadbeef3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl'
      )
      install_list = [{'location': 'file://' + location,
                       'location_type': 'file'}]
      with self.assertRaises(ValueError):
        install.fetch_packages(
          install_list, requester=requester, cache=cache, verbose=False)

      # The file is readily available, nothing should be copied to the cache.
      self.assertEqual(len(os.listdir(cache)), 0)

  def test_fetch_one_http_file_good(self):
    requester = FakeHttp()
    with util.temporary_directory(prefix='glyco-fetch-test-') as tempdir:
      cache = os.path.join(tempdir, 'cache')
      location = ('https://a.random.host.com/'
                  'source_package_valid_sha1-0.0.1-0_'
                  '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
      install_list = [{'location': location,
                       'location_type': 'http'}]
      paths = install.fetch_packages(
        install_list, requester=requester, cache=cache, verbose=False)

      cache_files = [os.path.join(cache, filename)
                     for filename in os.listdir(cache)]
      self.assertEqual(len(cache_files), 1)
      self.assertEqual(paths[0], cache_files[0])

  def test_fetch_one_http_file_invalid_sha1(self):
    requester = FakeHttp()
    with util.temporary_directory(prefix='glyco-fetch-test-') as tempdir:
      cache = os.path.join(tempdir, 'cache')
      location = ('https://a.random.host.com/'
                  'source_package_invalid_sha1-0.0.1-0_'
                  'deadbeef3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
      install_list = [{'location': location,
                       'location_type': 'http'}]
      with self.assertRaises(ValueError):
        install.fetch_packages(
          install_list, requester=requester, cache=cache, verbose=False)

      # An invalid file should be deleted from the cache.
      self.assertEqual(len(os.listdir(cache)), 0)

  def test_fetch_one_http_file_invalid_name(self):
    requester = FakeHttp()
    with util.temporary_directory(prefix='glyco-fetch-test-') as tempdir:
      cache = os.path.join(tempdir, 'cache')
      location = 'https://a.random.host.com/invalid_name.whl'
      install_list = [{'location': location,
                       'location_type': 'http'}]
      with self.assertRaises(ValueError):
        install.fetch_packages(
          install_list, requester=requester, cache=cache, verbose=False)

      # Still nothing in the cache
      self.assertEqual(len(os.listdir(cache)), 0)

  def test_fetch_one_http_file_http_error(self):
    requester = FakeHttp()
    with util.temporary_directory(prefix='glyco-fetch-test-') as tempdir:
      cache = os.path.join(tempdir, 'cache')
      location = ('https://a.broken.host.com/'
                  'source_package_valid_sha1-0.0.1-0_'
                  '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
      install_list = [{'location': location,
                       'location_type': 'http'}]
      with self.assertRaises(ValueError):
        install.fetch_packages(
          install_list, requester=requester, cache=cache, verbose=False)

      # Still nothing in the cache
      self.assertEqual(len(os.listdir(cache)), 0)


class GetInstallListTest(unittest.TestCase):
  def test_one_file(self):
    install_list = install.get_install_list([
      os.path.join(DATA_DIR, 'wheels', 'source_package_valid_sha1-0.0.1-0_'
                   '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
      ])

    self.assertEqual(len(install_list), 1)
    self.assertEqual(install_list[0]['location_type'], 'file')
    self.assertTrue(install_list[0]['location'].startswith('file://'))

  def test_two_files(self):
    install_list = install.get_install_list([
      os.path.join(DATA_DIR, 'wheels', 'source_package_valid_sha1-0.0.1-0_'
                   '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl'),
      os.path.join(DATA_DIR, 'wheels', 'source_package_invalid_sha1-0.0.1-0_'
                   'deadbeef3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
      ])

    self.assertEqual(len(install_list), 2)
    for item in install_list:
      self.assertEqual(item['location_type'], 'file')
      self.assertTrue(item['location'].startswith('file://'))

  def test_existing_and_non_existing_files(self):
    install_list = install.get_install_list([
        os.path.join(DATA_DIR, 'wheels', 'source_package_valid_sha1-0.0.1-0_'
                   '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl'),
        os.path.join(
          DATA_DIR, 'wheels', 'non_existing_file-0.0.1-0_'
              '41128a9c3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
      ])
    self.assertTrue(len(install_list), 2)
    self.assertFalse(install_list[0].get('error'))
    self.assertTrue(install_list[1].get('error'))

  def test_http_uri(self):
    install_list = install.get_install_list(
      ['http://some.host.com/some_package.whl'])
    self.assertTrue(len(install_list), 1)
    self.assertTrue(install_list[0].get('error'))

  def test_https_uri(self):
    install_list = install.get_install_list(
      ['https://some.host.com/some_package.whl'])

    self.assertEqual(len(install_list), 1)
    self.assertEqual(install_list[0]['location_type'], 'http')
    self.assertTrue(install_list[0]['location'].startswith('https://'))

  def test_gs_uri(self):
    install_list = install.get_install_list(
      ['gs://some_bucket/some_package.whl'])

    self.assertEqual(len(install_list), 1)
    self.assertEqual(install_list[0]['location_type'], 'http')
    self.assertEqual(
      install_list[0]['location'],
      'https://storage.googleapis.com/some_bucket/some_package.whl')

  def test_unknown_uri(self):
    install_list = install.get_install_list(
      ['weird://some.host.com/some_package.whl'])
    self.assertTrue(len(install_list), 1)
    self.assertTrue(install_list[0].get('error'))

if __name__ == '__main__':
  unittest.main()
