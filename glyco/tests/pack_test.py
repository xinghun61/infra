# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import ast
import os
import sys
import unittest

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'third_party'))

from glucose import main_
from glucose import pack
from glucose import util


class ParserTest(unittest.TestCase):
  # Test only pack-related options.
  def test_pack_zero_packages(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['pack'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

  def test_pack_one_package(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['pack', 'something'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

  def test_pack_two_packages(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['pack', 'something', 'another_thing'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

  def test_pack_two_packages_in_specific_dir(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['pack', 'something', 'another_thing',
                                 '--output-dir', 'wheel_directory'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))


class SetupPyGenerationTest(unittest.TestCase):
  def test_gen_setup_simple_case(self):
    content = pack.get_setup_py_content(os.path.join(DATA_DIR,
                                                     'simple_case_setup.cfg'))
    # Smoke test: make sure the result is valid Python
    ast.parse(content)

  def test_gen_setup_with_quotes(self):
    content = pack.get_setup_py_content(os.path.join(DATA_DIR,
                                                     'setup_with_quotes.cfg'))
    # Smoke test: make sure the result is valid Python
    ast.parse(content)

  def test_gen_setup_with_package_data(self):
    content = pack.get_setup_py_content(os.path.join(DATA_DIR,
                                                     'setup_with_quotes.cfg'))
    # Smoke test: make sure the result is valid Python
    ast.parse(content)


class PackPackagesTest(unittest.TestCase):
  def test_pack_local_package(self):
    with util.Virtualenv(prefix='glyco-pack-test-') as venv:
      with util.temporary_directory(
          prefix='glyco-pack-test-output-') as tempdir:
        path = pack.pack_local_package(venv,
                                       os.path.join(DATA_DIR, 'source_package'),
                                       tempdir)
        self.assertTrue(path.startswith(tempdir))

  def test_pack_bare_package(self):
    with util.Virtualenv(prefix='glyco-pack-test-') as venv:
      with util.temporary_directory('glyco-pack-test-output-') as tempdir:
        path = pack.pack_bare_package(
          venv,
          os.path.join(DATA_DIR, 'installed_package'),
          tempdir)
        self.assertTrue(path.startswith(tempdir))

  def test_pack(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    with util.temporary_directory(prefix='glyco-pack-test-') as tempdir:
      options = parser.parse_args(['pack',
                                   os.path.join(DATA_DIR, 'source_package'),
                                   os.path.join(DATA_DIR, 'installed_package'),
                                   '--output-dir', tempdir])
      # False is turned into the 0 (success) return code.
      self.assertFalse(pack.pack(options))
      self.assertEqual(len(os.listdir(tempdir)), 2)

  def test_pack_unhandled(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)

    with util.temporary_directory('glyco-pack-test-') as tempdir:
      # DATA_DIR is not a package at all.
      options = parser.parse_args(['pack', DATA_DIR, '--output-dir', tempdir])
      self.assertTrue(pack.pack(options))
      self.assertEqual(len(os.listdir(tempdir)), 0)

  def test_pack_partly_unhandled(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)

    with util.temporary_directory('glyco-pack-test-') as tempdir:
      options = parser.parse_args(['pack',
                                   DATA_DIR,
                                   os.path.join(DATA_DIR, 'source_package'),
                                   '--output-dir', tempdir])
      self.assertTrue(pack.pack(options))
      # We should not have generated any wheel.
      self.assertEqual(len(os.listdir(tempdir)), 0)

if __name__ == '__main__':
  unittest.main()
