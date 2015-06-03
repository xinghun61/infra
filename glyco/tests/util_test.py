# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'third_party'))

from glucose import util


class _UtilTestException(Exception):
  """Exception used inside tests."""


class TemporaryDirectoryTest(unittest.TestCase):
  def test_tempdir_no_error(self):
    with util.temporary_directory() as tempdir:
      self.assertTrue(os.path.isdir(tempdir))
      # This should work.
      with open(os.path.join(tempdir, 'test_tempdir_no_error.txt'), 'w') as f:
        f.write('nonsensical content')
    # And everything should have been cleaned up afterward
    self.assertFalse(os.path.isdir(tempdir))


  def test_tempdir_with_exception(self):
    try:
      with util.temporary_directory() as tempdir:
        self.assertTrue(os.path.isdir(tempdir))
        # Create a non-empty file to check that tempdir deletion works.
        with open(os.path.join(tempdir, 'test_tempdir_no_error.txt'), 'w') as f:
          f.write('nonsensical content')
        raise _UtilTestException()

    except _UtilTestException:
      pass  # this is supposed to happen
    else:
      raise AssertionError('No exception was raised')

    # And everything should have been cleaned up afterward
    self.assertFalse(os.path.isdir(tempdir))


if __name__ == '__main__':
  unittest.main()
