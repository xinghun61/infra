# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import shutil
import sys
import subprocess
import tempfile
import unittest
import zipfile

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'third_party'))

from glucose import main_
from glucose import selfpack


class ParserTest(unittest.TestCase):
  # Test only selfpack-related options.
  def test_selfpack_no_args(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)
    options = parser.parse_args(['selfpack'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

  def test_selfpack_with_output_file_short(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)

    options = parser.parse_args(['selfpack', '-o', 'weird_filename'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

    self.assertTrue(hasattr(options, 'output_file'))
    self.assertEqual(options.output_file, 'weird_filename')

  def test_selfpack_with_output_file_long(self):
    parser = argparse.ArgumentParser()
    main_.add_argparse_options(parser)

    options = parser.parse_args(['selfpack', '--output-file', 'other_filename'])
    self.assertTrue(hasattr(options, 'command'))
    self.assertTrue(callable(options.command))

    self.assertTrue(hasattr(options, 'output_file'))
    self.assertEqual(options.output_file, 'other_filename')


class SelfPackTest(unittest.TestCase):
  def test_selfpack(self):
    tempdir = None
    try:
      tempdir = tempfile.mkdtemp(prefix='glyco-test')
      options = argparse.Namespace()
      options.output_file = os.path.join(tempdir, 'test_selfpack.zip')

      # Not supposed to happen, just to be on the safe side.
      self.assertFalse(os.path.exists(options.output_file))

      selfpack.selfpack(options)
      self.assertTrue(os.path.exists(options.output_file))
      self.assertTrue(zipfile.is_zipfile(options.output_file))

      # Make some quick sanity checks. This is not sufficient to make sure the
      # zip file works.
      with zipfile.ZipFile(options.output_file, 'r') as f:
        namelist = f.namelist()
        self.assertIn('__main__.py', namelist)
        # TODO(pgervais): make sure this works on Windows.
        self.assertIn('glucose/__init__.py', namelist)
        # Comment must be empty for zip to be executable by Python.
        self.assertEqual(f.comment, '')

      # Smoke tests the file
      subprocess.check_call([sys.executable, options.output_file, '--help'])

    finally:
      if tempdir:
        shutil.rmtree(tempdir)


if __name__ == '__main__':
  unittest.main()
