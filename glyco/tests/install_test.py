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
    self.assertTrue(install.has_valid_sha1(filename))

  def test_bad_hash(self):
    filename = os.path.join(
      DATA_DIR, 'wheels', 'source_package_invalid_sha1-0.0.1-0_'
      + 'deadbeef3767ced3ec53b89b297e0268f1338b2b-py2-none-any.whl')
    self.assertFalse(install.has_valid_sha1(filename))

  def test_no_build_number(self):
    # The file doesn't have to exist.
    filename = ('source_package_invalid_sha1-0.0.1-py2-none-any.whl')
    with self.assertRaises(util.InvalidWheelFile):
      self.assertFalse(install.has_valid_sha1(filename))

  def test_invalid_filename(self):
    # The file doesn't have to exist.
    filename = ('source_package.txt')
    with self.assertRaises(util.InvalidWheelFile):
      self.assertFalse(install.has_valid_sha1(filename))


class InstallPackagesTest(unittest.TestCase):
  def test_install_one_package(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)

    with util.temporary_directory(prefix='glyco-install-test-') as tempdir:
      options = parser.parse_args(['pack',
                                   os.path.join(DATA_DIR, 'source_package'),
                                   '--output-dir', tempdir])
      wheel_paths = pack.pack(options)
      self.assertEqual(len(wheel_paths), 1)

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
      wheel_paths = pack.pack(options)
      self.assertEqual(len(wheel_paths), 2)

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


if __name__ == '__main__':
  unittest.main()
