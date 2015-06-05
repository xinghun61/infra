# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import subprocess
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'third_party'))

from glucose import main_
from glucose import pack
from glucose import util


def get_venv_python_path(env_path):
  # TODO: make that work on windows
  return os.path.join(env_path, 'bin', 'python')


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
    options = parser.parse_args(['pack', '--source-dir', 'something'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

  def test_pack_two_packages(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['pack', '--source-dir', 'something',
                                 '--source-dir', 'another_thing'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

  def test_pack_two_packages(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['pack', '--source-dir', 'something',
                                 '--source-dir', 'another_thing'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))


# These tests are rather slow, but because it's integration testing.
class VirtualEnvSetupTest(unittest.TestCase):
  def test_setup_virtualenv(self):
    with util.temporary_directory() as tempdir:
      pack.setup_virtualenv(tempdir, relocatable=False, activate=False)
      # Use a separate process instead of activating the virtualenv for
      # test isolation.

      # Check that modules from the virtualenv are used.
      output = subprocess.check_output(
        [get_venv_python_path(tempdir), '-c',
         'import wheel; print wheel.__file__'])
      self.assertTrue(output.startswith(tempdir))

  def test_setup_virtualenv_relocatable(self):
    with util.temporary_directory() as tempdir:
      pack.setup_virtualenv(tempdir, relocatable=True, activate=False)
      # Use a separate process instead of activating the virtualenv for
      # test isolation.

      # Check that modules from the virtualenv are used.
      output = subprocess.check_output(
        [get_venv_python_path(tempdir), '-c',
         'import wheel; print wheel.__file__'])
      self.assertTrue(output.startswith(tempdir))


if __name__ == '__main__':
  unittest.main()
