# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis import parse_util
from analysis.type_enums import CallStackFormatType
from libs.deps.dependency import Dependency

from testing_utils import testing


class ParseUtilTest(testing.AppengineTestCase):

  def testGetFullPathForJavaFrame(self):
    self.assertEqual(parse_util.GetFullPathForJavaFrame(
        'classA.classB.function'), 'classA/classB.java')
    self.assertEqual(
        parse_util.GetFullPathForJavaFrame(
            'org.chromium.chrome.browser.file.function'),
        'src/chrome/android/java/src/org/chromium/chrome/browser/file.java')

  def testGetCrashedLineRange(self):
    self.assertEqual(parse_util.GetCrashedLineRange('23'),
                     [23])
    self.assertEqual(parse_util.GetCrashedLineRange('23:2'),
                     [23, 24, 25])

  def testGetDepPathAndNormalizedFilePath(self):
    deps = {'src': Dependency('src', 'https://repo', '1'),
            'src/Upper': Dependency('src/Upper', 'https://repo_upper', '2')}

    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('out/r/gen/b.cc', deps),
        ('', 'out/r/gen/b.cc', None))
    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('src/a/b.cc', deps),
        ('src', 'a/b.cc', 'https://repo'))

    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('src/Upper/a/b.cc', deps),
        ('src/Upper', 'a/b.cc', 'https://repo_upper'))
    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('src/upper/a/b.cc', deps),
        ('src/Upper', 'a/b.cc', 'https://repo_upper'))
    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('Upper/a/b.cc', deps),
        ('src/Upper', 'a/b.cc', 'https://repo_upper'))
    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('upper/a/b.cc', deps),
        ('src/Upper', 'a/b.cc', 'https://repo_upper'))
    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath(
            'upperdummy/a/b.cc', deps, root_path='src_root',
            root_repo_url='https://root'),
        ('src_root', 'upperdummy/a/b.cc', 'https://root'))

    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('dummy/path/b.cc', deps),
        ('src', 'dummy/path/b.cc', parse_util.CHROMIUM_REPO_URL))

    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('a.java', deps,
                                                   is_java=True),
        ('', 'a.java', None))

  def testGetDepPathAndNormalizedFilePathSplitLongPathByDepPath(self):
    """Tests ``GetDepPathAndNormalizedFilePath`` split long path by dep path."""
    deps = {'src': Dependency('src', 'https://repo', '1'),
            'src/Upper': Dependency('src/Upper', 'https://repo', '2')}

    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('a/b/c/src/d/h.cc', deps),
        ('src', 'd/h.cc', 'https://repo'))

    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('a/src/upper/b/c.h', deps),
        ('src/Upper', 'b/c.h', 'https://repo'))
