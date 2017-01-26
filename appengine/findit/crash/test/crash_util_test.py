# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash import crash_util
from testing_utils import testing


class CrashUtilTest(testing.AppengineTestCase):

  def testIsSameFilePath(self):
    path_1 = 'third_party/a/b/c/file.cc'
    path_2 = 'third_party/a/file.cc'

    self.assertTrue(crash_util.IsSameFilePath(path_1, path_2))

    path_1 = 'a/b/c/file.cc'
    path_2 = 'a/b/c/file2.cc'

    self.assertFalse(crash_util.IsSameFilePath(path_1, path_2))

    path_1 = 'a/b/c/d/e/file.cc'
    path_2 = 'f/g/file.cc'

    self.assertTrue(crash_util.IsSameFilePath(None, None))
    self.assertFalse(crash_util.IsSameFilePath(path_1, path_2))
    self.assertFalse(crash_util.IsSameFilePath(None, path_2))
    self.assertFalse(crash_util.IsSameFilePath(path_1, None))
