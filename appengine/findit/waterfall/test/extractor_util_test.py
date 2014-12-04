# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import unittest

from waterfall import extractor_util


class ExtractorUtilTest(unittest.TestCase):
  def _VerifyPattern(self, pattern, cases):
    self.assertTrue(isinstance(cases, (list, dict)))

    if isinstance(pattern, (str, basestring)):
      p = re.compile(r'(%s)' % pattern)
    else:
      p = pattern

    for case in cases:
      if isinstance(cases, list):
        expected_result = [case]
      else:
        expected_result = cases[case]
      result = p.findall(case)
      self.assertEqual(expected_result, result, 'Failed case: "%s"' % case)

  def testPathSeparatorPattern(self):
    self._VerifyPattern(
        extractor_util.PATH_SEPARATOR_PATTERN,
        ['\\', '\\\\', '/', '//'])

  def testFileNamePattern(self):
    self._VerifyPattern(
        extractor_util.FILE_NAME_PATTERN,
        ['.', '..', 'abc123', 'third_party', 'libc++', 'abc-def', 'a.b'])

  def testFileExtensionPattern(self):
    self._VerifyPattern(
        extractor_util.FILE_EXTENSION_PATTERN,
        extractor_util.SUPPORTED_FILE_EXTENSIONS)

  def testRootDirPattern(self):
    self._VerifyPattern(
        extractor_util.ROOT_DIR_PATTERN,
        ['/', 'c:\\\\', 'c:/', 'C://'])

  def testFilePathLinePattern(self):
    cases = {
        'at Object.Test.runAccessibilityAudit (test_api.js:315:17)':
            [('test_api.js', '315')],
        'FATAL:content_setting_bubble_cocoa.mm(286)] Check failed: false.':
            [('content_setting_bubble_cocoa.mm', '286')],
        ' src/third_party/libc++/trunk/include/complex.h ':
            [('src/third_party/libc++/trunk/include/complex.h', '')],
        'Cacher at tools/telemetry/telemetry/decorators.py:31':
            [('tools/telemetry/telemetry/decorators.py', '31')],
        'content/browser/appcache/appcache_manifest_parser.cc':
            [('content/browser/appcache/appcache_manifest_parser.cc', '')],
        'included from ../../base/memory/weak_ptr.h:68:0,':
            [('../../base/memory/weak_ptr.h', '68')],
        'blabla E:\\a\\.\\b\\..\\c\\d.txt(blabla)':
            [('E:\\a\\.\\b\\..\\c\\d.txt', '')],
        'blabla /a/b/../../c/./d.cc':
            [('/a/b/../../c/./d.cc', '')],
        'libgfx.a(gfx.render_text_harfbuzz.o)':
            [('gfx.render_text_harfbuzz.o', '')],
        'blabla a/b.cpp:234 include c/d.h':
            [('a/b.cpp', '234'), ('c/d.h', '')],
    }
    self._VerifyPattern(extractor_util.FILE_PATH_LINE_PATTERN, cases)

  def testPythonStackTracePattern(self):
    cases = {
        '  File "a/b/c.py", line 109, in abc':
            [('a/b/c.py', '109', 'abc')],
    }
    self._VerifyPattern(extractor_util.PYTHON_STACK_TRACE_PATTERN, cases)

  def testChromiumSrcPattern(self):
    cases = {
        '/b/build/slave/Android_Tests/build/src/a/b/c.py': ['a/b/c.py'],
        'c:/b/build/slave/win_builder/build/src/d/e/f.cc': ['d/e/f.cc'],
    }
    self._VerifyPattern(extractor_util.CHROMIUM_SRC_PATTERN, cases)

  def testNormalizeFilePath(self):
    cases = {
        '../a/b/c.cc': 'a/b/c.cc',
        'a/b/./c.cc': 'a/b/c.cc',
        'a/b/../c.cc': 'a/c.cc',
        'a\\b\\.\\c.cc': 'a/b/c.cc',
        'a\\\\b\\\\c.cc': 'a/b/c.cc',
        '/b/build/slave/Android_Tests/build/src/a/b/c.cc': 'a/b/c.cc',
        'c:\\\\b\\build\\slave\\win_builder\\build\\src\\d\\\\e.cc': 'd/e.cc',
    }
    for case in cases:
      self.assertEqual(extractor_util.NormalizeFilePath(case), cases[case])

  def testShouldIgnoreLine(self):
    cases = {
        'application_loader.h(11) : fatal error C1083: Cannot open...': False,
        '35:WARNING:data_reduction_proxy_settings.cc(328)] SPDY proxy': True,
        '36:ERROR:desktop_window_tree_host_x11.cc(810)] Not implemented': True,
        '09:INFO:CONSOLE(0)] "[SUCCESS] ... /test.js (98)': True,
    }
    for case in cases:
      self.assertEqual(extractor_util.ShouldIgnoreLine(case), cases[case])
