# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.dependency import Dependency
from crash import parse_util
from crash.type_enums import CallStackFormatType, CallStackLanguageType

from testing_utils import testing


class ParseUtilTest(testing.AppengineTestCase):

  def testGetFullPathForJavaFrame(self):
    self.assertEqual(parse_util.GetFullPathForJavaFrame(
        'classA.classB.function'), 'classA/classB.java')

  def testGetCrashedLineRange(self):
    self.assertEqual(parse_util.GetCrashedLineRange('23'),
                     [23])
    self.assertEqual(parse_util.GetCrashedLineRange('23:2'),
                     [23, 24, 25])

  def testGetDepPathAndNormalizedFilePath(self):
    deps = {'src/': Dependency('src/', 'https://repo', '1'),
            'src/Upper/': Dependency('src/Upper', 'https://repo', '2')}

    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('out/r/gen/b.cc', deps),
        ('', 'out/r/gen/b.cc'))
    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('src/a/b.cc', deps),
        ('src/', 'a/b.cc'))
    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('src/Upper/a/b.cc', deps),
        ('src/Upper/', 'a/b.cc'))

    self.assertEqual(
        parse_util.GetDepPathAndNormalizedFilePath('dummy/path/b.cc', deps),
        ('', 'dummy/path/b.cc'))


  def testGetLanguageTypeFromFormatType(self):
    self.assertEqual(
        parse_util.GetLanguageTypeFromFormatType(CallStackFormatType.JAVA),
        CallStackLanguageType.JAVA)

    self.assertEqual(
        parse_util.GetLanguageTypeFromFormatType(CallStackFormatType.SYZYASAN),
        CallStackLanguageType.CPP)

    self.assertEqual(
        parse_util.GetLanguageTypeFromFormatType(CallStackFormatType.DEFAULT),
        CallStackLanguageType.CPP)
