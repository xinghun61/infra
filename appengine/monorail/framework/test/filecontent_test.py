# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the filecontent module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import filecontent


class MimeTest(unittest.TestCase):
  """Test methods for the mime module."""

  _TEST_EXTENSIONS_TO_CTYPES = {
      'html': 'text/plain',
      'htm': 'text/plain',
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
      'pdf': 'application/pdf',
  }

  _CODE_EXTENSIONS = [
      'py', 'java', 'mf', 'bat', 'sh', 'php', 'vb', 'pl', 'sql',
      'patch', 'diff',
  ]

  def testCommonExtensions(self):
    """Tests some common extensions for their expected content types."""
    for ext, ctype in self._TEST_EXTENSIONS_TO_CTYPES.items():
      self.assertEqual(
          filecontent.GuessContentTypeFromFilename('file.%s' % ext),
          ctype)

  def testCaseDoesNotMatter(self):
    """Ensure that case (upper/lower) of extension does not matter."""
    for ext, ctype in self._TEST_EXTENSIONS_TO_CTYPES.items():
      ext = ext.upper()
      self.assertEqual(
          filecontent.GuessContentTypeFromFilename('file.%s' % ext),
          ctype)

    for ext in self._CODE_EXTENSIONS:
      ext = ext.upper()
      self.assertEqual(
          filecontent.GuessContentTypeFromFilename('code.%s' % ext),
          'text/plain')

  def testCodeIsText(self):
    """Ensure that code extensions are text/plain."""
    for ext in self._CODE_EXTENSIONS:
      self.assertEqual(
          filecontent.GuessContentTypeFromFilename('code.%s' % ext),
          'text/plain')

  def testNoExtensionIsText(self):
    """Ensure that no extension indicates text/plain."""
    self.assertEqual(
        filecontent.GuessContentTypeFromFilename('noextension'),
        'text/plain')

  def testUnknownExtension(self):
    """Ensure that an obviously unknown extension returns is binary."""
    self.assertEqual(
        filecontent.GuessContentTypeFromFilename('f.madeupextension'),
        'application/octet-stream')

  def testNoShockwaveFlash(self):
    """Ensure that Shockwave files will NOT be served w/ that content type."""
    self.assertEqual(
        filecontent.GuessContentTypeFromFilename('bad.swf'),
        'application/octet-stream')


class DecodeFileContentsTest(unittest.TestCase):

  def IsBinary(self, contents):
    _contents, is_binary, _is_long = (
        filecontent.DecodeFileContents(contents))
    return is_binary

  def testFileIsBinaryEmpty(self):
    self.assertFalse(self.IsBinary(''))

  def testFileIsBinaryShortText(self):
    self.assertFalse(self.IsBinary('This is some plain text.'))

  def testLineLengthDetection(self):
    unicode_str = (
        u'Some non-ascii chars - '
        u'\xa2\xfa\xb6\xe7\xfc\xea\xd0\xf4\xe6\xf0\xce\xf6\xbe')
    short_line = unicode_str.encode('iso-8859-1')
    long_line = (unicode_str * 100)[:filecontent._MAX_SOURCE_LINE_LEN_LOWER+1]
    long_line = long_line.encode('iso-8859-1')

    lines = [short_line] * 100
    lines.append(long_line)

    # High lower ratio - text
    self.assertFalse(self.IsBinary('\n'.join(lines)))

    lines.extend([long_line] * 99)

    # 50/50 lower/upper ratio - binary
    self.assertTrue(self.IsBinary('\n'.join(lines)))

    # Single line too long - binary
    lines = [short_line] * 100
    lines.append(short_line * 100)  # Very long line
    self.assertTrue(self.IsBinary('\n'.join(lines)))

  def testFileIsBinaryLongText(self):
    self.assertFalse(self.IsBinary('This is plain text. \n' * 100))
    # long utf-8 lines are OK
    self.assertFalse(self.IsBinary('This one long line. ' * 100))

  def testFileIsBinaryLongBinary(self):
    bin_string = ''.join([chr(c) for c in range(122, 252)])
    self.assertTrue(self.IsBinary(bin_string * 100))

  def testFileIsTextByPath(self):
    bin_string = ''.join([chr(c) for c in range(122, 252)] * 100)
    unicode_str = (
        u'Some non-ascii chars - '
        u'\xa2\xfa\xb6\xe7\xfc\xea\xd0\xf4\xe6\xf0\xce\xf6\xbe')
    long_line = (unicode_str * 100)[:filecontent._MAX_SOURCE_LINE_LEN_LOWER+1]
    long_line = long_line.encode('iso-8859-1')

    for contents in [bin_string, long_line]:
      self.assertTrue(filecontent.DecodeFileContents(contents, path=None)[1])
      self.assertTrue(filecontent.DecodeFileContents(contents, path='')[1])
      self.assertTrue(filecontent.DecodeFileContents(contents, path='foo')[1])
      self.assertTrue(
          filecontent.DecodeFileContents(contents, path='foo.bin')[1])
      self.assertTrue(
          filecontent.DecodeFileContents(contents, path='foo.zzz')[1])
      for path in ['a/b/Makefile.in', 'README', 'a/file.js', 'b.txt']:
        self.assertFalse(
            filecontent.DecodeFileContents(contents, path=path)[1])

  def testFileIsBinaryByCommonExtensions(self):
    contents = 'this is not examined'
    self.assertTrue(filecontent.DecodeFileContents(
        contents, path='junk.zip')[1])
    self.assertTrue(filecontent.DecodeFileContents(
        contents, path='JUNK.ZIP')[1])
    self.assertTrue(filecontent.DecodeFileContents(
        contents, path='/build/HelloWorld.o')[1])
    self.assertTrue(filecontent.DecodeFileContents(
        contents, path='/build/Hello.class')[1])
    self.assertTrue(filecontent.DecodeFileContents(
        contents, path='/trunk/libs.old/swing.jar')[1])

    self.assertFalse(filecontent.DecodeFileContents(
        contents, path='HelloWorld.cc')[1])
    self.assertFalse(filecontent.DecodeFileContents(
        contents, path='Hello.java')[1])
    self.assertFalse(filecontent.DecodeFileContents(
        contents, path='README')[1])
    self.assertFalse(filecontent.DecodeFileContents(
        contents, path='READ.ME')[1])
    self.assertFalse(filecontent.DecodeFileContents(
        contents, path='README.txt')[1])
    self.assertFalse(filecontent.DecodeFileContents(
        contents, path='README.TXT')[1])
    self.assertFalse(filecontent.DecodeFileContents(
        contents, path='/trunk/src/com/monorail/Hello.java')[1])
    self.assertFalse(filecontent.DecodeFileContents(
        contents, path='/branches/1.2/resource.el')[1])
    self.assertFalse(filecontent.DecodeFileContents(
        contents, path='/wiki/PageName.wiki')[1])

  def testUnreasonablyLongFile(self):
    contents = '\n' * (filecontent.SOURCE_FILE_MAX_LINES + 2)
    _contents, is_binary, is_long = filecontent.DecodeFileContents(
        contents)
    self.assertFalse(is_binary)
    self.assertTrue(is_long)

    contents = '\n' * 100
    _contents, is_binary, is_long = filecontent.DecodeFileContents(
        contents)
    self.assertFalse(is_binary)
    self.assertFalse(is_long)
