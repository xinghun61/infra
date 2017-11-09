# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from services import files
from waterfall.test import wf_testcase


class FilesTest(wf_testcase.WaterfallTestCase):

  def testIsSameFile(self):
    self.assertTrue(files.IsSameFile('a/b/x.cc', 'x.cc'))
    self.assertTrue(files.IsSameFile('a/b/x.cc', 'b/x.cc'))
    self.assertTrue(files.IsSameFile('a/b/x.cc', 'a/b/x.cc'))
    self.assertTrue(files.IsSameFile('A/B/X.cc', 'a/b/x.cc'))

    self.assertFalse(
        files.IsSameFile('a/prefix_x.cc.', 'x.cc'))
    self.assertFalse(
        files.IsSameFile('prefix_a/x.cc.', 'a/x.cc'))
    self.assertFalse(
        files.IsSameFile('c/x.cc.', 'a/b/c/x.cc'))
    self.assertFalse(files.IsSameFile('a/x.cc.', 'a/y.cc'))

  def testNormalizeObjectFile(self):
    cases = {
        'obj/a/T.x.o': 'a/x.o',
        'obj/a/T.x.y.o': 'a/x.y.o',
        'x.o': 'x.o',
        'obj/a/x.obj': 'a/x.obj',
        'a.cc.obj': 'a.cc.obj',
        'T.a.c.o': 'a.c.o',
        'T.a.o': 'a.o'
    }
    for obj_file, expected_file in cases.iteritems():
      self.assertEqual(
          expected_file,
          files._NormalizeObjectFilePath(obj_file))

  def testStripCommonSuffix(self):
    cases = {
        'a_file':
            'a_file_%s.cc' % '_'.join(files._COMMON_SUFFIXES),
        'src/b_file':
            'src/b_file_impl_mac.h',
        'c_file':
            'c_file_browsertest.cc',
        'xdtest':
            'xdtest.cc',
    }
    for expected_file, file_path in cases.iteritems():
      self.assertEqual(
          expected_file,
          files._StripExtensionAndCommonSuffix(file_path))

  def testIsRelated(self):
    self.assertTrue(files.IsRelated('a.py', 'a_test.py'))
    self.assertTrue(files.IsRelated('a.h', 'a_impl_test.o'))
    self.assertTrue(
        files.IsRelated('a.h', 'target.a_impl_test.obj'))

    self.assertFalse(files.IsRelated('a/x.cc', 'a/b/y.cc'))
    self.assertFalse(files.IsRelated('a/x.cc', 'xdtest.cc'))
    self.assertFalse(
        files.IsRelated('a_tests.cc', 'a_browsertests.cc'))
    self.assertFalse(
        files.IsRelated('cc_unittests.isolate', 'a.cc.obj'))
    self.assertFalse(files.IsRelated('a.h', 'a.pyc'))
    self.assertFalse(files.IsRelated('a', 'b'))
    self.assertFalse(files.IsRelated('a', 'a'))

  def testStripChromiumRootDirectory(self):
    self.assertEqual('abc.cc', files.StripChromiumRootDirectory('src/abc.cc'))

  def testStripChromiumRootDirectoryNoSrc(self):
    self.assertEqual('abc.cc', files.StripChromiumRootDirectory('abc.cc'))