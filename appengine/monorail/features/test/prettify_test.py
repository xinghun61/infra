# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the prettify module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from third_party import ezt

from features import prettify


class SourceBrowseTest(unittest.TestCase):

  def testPrepareSourceLinesForHighlighting(self):
    # String representing an empty source file
    src = ''

    file_lines = prettify.PrepareSourceLinesForHighlighting(src)
    self.assertEqual(len(file_lines), 0)

  def testPrepareSourceLinesForHighlightingNoBreaks(self):
    # seven lines of text with no blank lines
    src = ' 1\n 2\n 3\n 4\n 5\n 6\n 7'

    file_lines = prettify.PrepareSourceLinesForHighlighting(src)
    self.assertEqual(len(file_lines), 7)
    out_lines = [fl.line for fl in file_lines]
    self.assertEqual('\n'.join(out_lines), src)

    file_lines = prettify.PrepareSourceLinesForHighlighting(src)
    self.assertEqual(len(file_lines), 7)

  def testPrepareSourceLinesForHighlightingWithBreaks(self):
    # seven lines of text with line 5 being blank
    src = ' 1\n 2\n 3\n 4\n\n 6\n 7'

    file_lines = prettify.PrepareSourceLinesForHighlighting(src)
    self.assertEqual(len(file_lines), 7)


class BuildPrettifyDataTest(unittest.TestCase):

  def testNonSourceFile(self):
    prettify_data = prettify.BuildPrettifyData(0, '/dev/null')
    self.assertDictEqual(
        dict(should_prettify=ezt.boolean(False),
             prettify_class=None),
        prettify_data)

    prettify_data = prettify.BuildPrettifyData(10, 'readme.txt')
    self.assertDictEqual(
        dict(should_prettify=ezt.boolean(False),
             prettify_class=None),
        prettify_data)

  def testGenericLanguage(self):
    prettify_data = prettify.BuildPrettifyData(123, 'trunk/src/hello.php')
    self.assertDictEqual(
        dict(should_prettify=ezt.boolean(True),
             prettify_class=''),
        prettify_data)

  def testSpecificLanguage(self):
    prettify_data = prettify.BuildPrettifyData(123, 'trunk/src/hello.java')
    self.assertDictEqual(
        dict(should_prettify=ezt.boolean(True),
             prettify_class='lang-java'),
        prettify_data)

  def testThirdPartyExtensionLanguages(self):
    for ext in ['apollo', 'agc', 'aea', 'el', 'scm', 'cl', 'lisp',
                'go', 'hs', 'lua', 'fs', 'ml', 'proto', 'scala',
                'sql', 'vb', 'vbs', 'vhdl', 'vhd', 'wiki', 'yaml',
                'yml', 'clj']:
      prettify_data = prettify.BuildPrettifyData(123, '/trunk/src/hello.' + ext)
      self.assertDictEqual(
          dict(should_prettify=ezt.boolean(True),
               prettify_class='lang-' + ext),
          prettify_data)

  def testExactFilename(self):
    prettify_data = prettify.BuildPrettifyData(123, 'trunk/src/Makefile')
    self.assertDictEqual(
        dict(should_prettify=ezt.boolean(True),
             prettify_class='lang-sh'),
        prettify_data)
