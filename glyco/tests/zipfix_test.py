# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import os
import sys
import unittest
import zipfile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'third_party'))

from glucose import pack
from glucose import util
from glucose import zipfix


class ResetTimestampTest(unittest.TestCase):
  def test_reset_timestamps(self):
    with util.temporary_directory(prefix='glyco-zipfix-') as tempdir:
      # Create an archive
      zipname = os.path.join(tempdir, 'testfile.zip')
      with zipfile.ZipFile(zipname, 'w') as f:
        f.write(os.path.join(DATA_DIR, 'zipfix_test', 'file1.txt'))
        f.write(os.path.join(DATA_DIR, 'zipfix_test', 'file2.txt'))

      # Read original state
      with zipfile.ZipFile(zipname, 'r') as f:
        dt_orig = [info.date_time for info in f.infolist()]
        namelist_orig = f.namelist()
        namelist_orig.sort()
        hashes_orig = [hashlib.sha1(f.read(filename)).hexdigest()
                       for filename in namelist_orig]

      # Reset
      zipfix.reset_all_timestamps_in_zip(zipname)

      # Make sure only timestamps have changed.
      with zipfile.ZipFile(zipname, 'r') as f:
        dt_new = [info.date_time for info in f.infolist()]
        namelist_new = f.namelist()
        namelist_new.sort()
        hashes_new = [hashlib.sha1(f.read(filename)).hexdigest()
                      for filename in namelist_new]

      self.assertEqual(namelist_orig, namelist_new)
      self.assertEqual(hashes_orig, hashes_new)
      self.assertNotEqual(dt_orig, dt_new)
      for dt in dt_new:
        self.assertEqual(dt, (1980, 0, 0, 0, 0, 0))


if __name__ == '__main__':
  unittest.main()
