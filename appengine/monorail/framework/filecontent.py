# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Utility routines for dealing with MIME types and decoding text files."""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import itertools
import logging

from framework import framework_constants


_EXTENSION_TO_CTYPE_TABLE = {
    # These are images/PDFs that we trust the browser to display.
    'gif': 'image/gif',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'webp': 'image/webp',
    'ico': 'image/x-icon',
    'svg': 'image/svg+xml',
    'pdf': 'application/pdf',
    'ogv': 'video/ogg',
    'mov': 'video/quicktime',
    'mp4': 'video/mp4',
    'mpg': 'video/mp4',
    'mpeg': 'video/mp4',
    'webm': 'video/webm',

    # We do not serve mimetypes that cause the brower to launch a local
    # app because that is not required for issue tracking and it is a
    # potential security risk.
}


def GuessContentTypeFromFilename(filename):
  """Guess a file's content type based on the filename extension.

  Args:
    filename: String name of a file.

  Returns:
    MIME type string to use when serving this file.  We only use text/plain for
    text files, appropriate image content-types, or application/octet-stream
    for virtually all binary files.  This limits the richness of the user's
    experience, e.g., the user cannot open an MS Office application directly
    by clicking on an attachment, but it is safer.
  """
  ext = filename.split('.')[-1] if ('.' in filename) else ''
  ext = ext.lower()
  if ext in COMMON_TEXT_FILE_EXTENSIONS:
    return 'text/plain'
  return _EXTENSION_TO_CTYPE_TABLE.get(ext.lower(), 'application/octet-stream')


# Constants used in detecting if a file has binary content.
# All line lengths must be below the upper limit, and there must be a spefic
# ratio below the lower limit.
_MAX_SOURCE_LINE_LEN_LOWER = 350
_MAX_SOURCE_LINE_LEN_UPPER = 800
_SOURCE_LINE_LEN_LOWER_RATIO = 0.9

# Message to display for undecodable commit log or author values.
UNDECODABLE_LOG_CONTENT = '[Cannot be displayed]'

# How large a repository file is in bytes before we don't try to display it
SOURCE_FILE_MAX_SIZE = 1000 * 1024
SOURCE_FILE_MAX_LINES = 50000

# The source code browser will not attempt to display any filename ending
# with one of these extensions.
COMMON_BINARY_FILE_EXTENSIONS = {
    'gif', 'jpg', 'jpeg', 'psd', 'ico', 'icon', 'xbm', 'xpm', 'xwd', 'pcx',
    'bmp', 'png', 'vsd,' 'mpg', 'mpeg', 'wmv', 'wmf', 'avi', 'flv', 'snd',
    'mp3', 'wma', 'exe', 'dll', 'bin', 'class', 'o', 'so', 'lib', 'dylib',
    'jar', 'ear', 'war', 'par', 'msi', 'tar', 'zip', 'rar', 'cab', 'z', 'gz',
    'bz2', 'dmg', 'iso', 'rpm', 'pdf', 'eps', 'tif', 'tiff', 'xls', 'ppt',
    'graffie', 'violet', 'webm', 'webp',
    }

# The source code browser will display file contents as text data for files
# with the following extensions or exact filenames (assuming they decode
# correctly).
COMMON_TEXT_FILE_EXTENSIONS = (
    set(framework_constants.PRETTIFY_CLASS_MAP.keys()) |
    { '', 'ada', 'asm', 'asp', 'bat', 'cgi', 'csv', 'diff', 'el', 'emacs',
      'jsp', 'log', 'markdown', 'md', 'mf', 'patch', 'plist', 'properties', 'r',
      'rc', 'txt', 'vim', 'wiki', 'xemacs', 'yacc',
      })
COMMON_TEXT_FILENAMES = (
    set(framework_constants.PRETTIFY_FILENAME_CLASS_MAP.keys()) |
    {'authors', 'install', 'readme'})


def DecodeFileContents(file_contents, path=None):
  """Try converting file contents to unicode using utf-8 or latin-1.

  This is applicable to untrusted maybe-text from vcs files or inbound emails.

  We try decoding the file as utf-8, then fall back on latin-1. In the former
  case, we call the file a text file; in the latter case, we guess whether
  the file is text or binary based on line length.

  If we guess text when the file is binary, the user sees safely encoded
  gibberish. If the other way around, the user sees a message that we will
  not display the file.

  TODO(jrobbins): we could try the user-supplied encoding, iff it
  is one of the encodings that we know that we can handle.

  Args:
    file_contents: byte string from uploaded file.  It could be text in almost
      any encoding, or binary.  We cannot trust the user-supplied encoding
      in the mime-type property.
    path: string pathname of file.

  Returns:
    The tuple (unicode_string, is_binary, is_long):
      - The unicode version of the string.
      - is_binary is true if the string could not be decoded as text.
      - is_long is true if the file has more than SOURCE_FILE_MAX_LINES lines.
  """
  # If the filename is one that typically identifies a binary file, then
  # just treat it as binary without any further analysis.
  ext = None
  if path and '.' in path:
    ext = path.split('.')[-1]
    if ext.lower() in COMMON_BINARY_FILE_EXTENSIONS:
      # If the file is binary, we don't care about the length, since we don't
      # show or diff it.
      return u'', True, False

  # If the string can be decoded as utf-8, we treat it as textual.
  try:
    u_str = file_contents.decode('utf-8', 'strict')
    is_long = len(u_str.split('\n')) > SOURCE_FILE_MAX_LINES
    return u_str, False, is_long
  except UnicodeDecodeError:
    logging.info('not a utf-8 file: %s bytes', len(file_contents))

  # Fall back on latin-1. This will always succeed, since every byte maps to
  # something in latin-1, even if that something is gibberish.
  u_str = file_contents.decode('latin-1', 'strict')

  lines = u_str.split('\n')
  is_long = len(lines) > SOURCE_FILE_MAX_LINES
  # Treat decodable files with certain filenames and/or extensions as text
  # files. This avoids problems with common file types using our text/binary
  # heuristic rules below.
  if path:
    name = path.split('/')[-1]
    if (name.lower() in COMMON_TEXT_FILENAMES or
        (ext and ext.lower() in COMMON_TEXT_FILE_EXTENSIONS)):
      return u_str, False, is_long

  # HEURISTIC: Binary files can qualify as latin-1, so we need to
  # check further.  Any real source code is going to be divided into
  # reasonably sized lines. All lines must be below an upper character limit,
  # and most lines must be below a lower limit. This allows some exceptions
  # to the lower limit, but is more restrictive than just using a single
  # large character limit.
  is_binary = False
  lower_count = 0
  for line in itertools.islice(lines, SOURCE_FILE_MAX_LINES):
    size = len(line)
    if size <= _MAX_SOURCE_LINE_LEN_LOWER:
      lower_count += 1
    elif size > _MAX_SOURCE_LINE_LEN_UPPER:
      is_binary = True
      break

  ratio = lower_count / float(max(1, len(lines)))
  if ratio < _SOURCE_LINE_LEN_LOWER_RATIO:
    is_binary = True

  return u_str, is_binary, is_long
