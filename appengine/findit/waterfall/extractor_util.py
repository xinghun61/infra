# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re


# File extensions to filter out files from log.
SUPPORTED_FILE_EXTENSIONS = [
    'c',
    'cc',
    'cpp',
    'css',
    'exe',
    'gn',
    'gyp',
    'gypi',
    'h',
    'hh',
    'html',
    'idl',
    'isolate',
    'java',
    'js',
    'json',
    'mm',
    'mojom',
    'o',
    'obj',
    'py',
    'pyc',
    'sh',
    'sha1',
    'txt',
]


# Match file path separator: "/", "//", "\", "\\".
PATH_SEPARATOR_PATTERN = r'(?:/{1,2}|\\{1,2})'


# Match file/directory names, ".", and "..".
# Some file/directory name may contain ' ', but it leads to noise if we try to
# match them, so ignore for now.
FILE_NAME_PATTERN = r'[\w+.-]+'


# Match supported file extensions.
# Sort extension list to avoid non-full match like 'c' matching 'c' in 'cpp'.
FILE_EXTENSION_PATTERN = (r'(?:%s)' %
    '|'.join(sorted(SUPPORTED_FILE_EXTENSIONS, reverse=True)))


# Match drive root directory on Windows, like "C:/" or "C:\\".
WINDOWS_ROOT_PATTERN = r'[a-zA-Z]:{SEP}'.format(SEP=PATH_SEPARATOR_PATTERN)


# Match system root directory on Linux/Mac.
UNIX_ROOT_PATTERN = r'/+'


# Match system/drive root on Linux/Mac/Windows.
ROOT_DIR_PATTERN = r'(?:{WIN_ROOT}|{UNIX_ROOT})'.format(
    WIN_ROOT=WINDOWS_ROOT_PATTERN, UNIX_ROOT=UNIX_ROOT_PATTERN)


# Match a full file path and line number.
# It could match files with or without line numbers like below:
#   c:\\a\\b.txt:12
#   c:\a\b.txt(123)
#   D:/a/b.txt
#   /a/../b/./c.txt
#   a/b/c.txt
#   'gfx.render_text_harfbuzz.o' in "libgfx.a(gfx.render_text_harfbuzz.o)"
#   //BUILD.gn:246
FILE_PATH_LINE_PATTERN = re.compile((
    r'(?:^|[^\w/\\.]+)'  # Non-path characters.
    r'('
    r'{ROOT_DIR}?'  # System/Drive root directory.
    r'(?:{FILE_NAME}{SEP})*'  # Directories.
    r'{FILE_NAME}\.{FILE_EXTENSION}'  # File name and extension.
    r')'
    r'(?:[\(:](\d+))?'  # Line number might not be available.
    r'(?=\W+|$)'  # Non-path characters, match but no consume.
    ).format(
        ROOT_DIR=ROOT_DIR_PATTERN,
        FILE_NAME=FILE_NAME_PATTERN,
        SEP=PATH_SEPARATOR_PATTERN,
        FILE_EXTENSION=FILE_EXTENSION_PATTERN))


# Pattern for Python stack trace frame.
PYTHON_STACK_TRACE_FRAME_PATTERN = re.compile(
    r'\s*File "(?P<file>.+\.py)", line (?P<line>[0-9]+), in (?P<function>.+)')


# Pattern for C++ stack trace frame.
CPP_STACK_TRACE_FRAME_PATTERN = re.compile('\s*#(\d+) 0x[0-9a-fA-F]+ .*')


# Match the file path relative to the root src of a chromium repo checkout.
CHROMIUM_SRC_PATTERN = re.compile(
    r'.*/build/slave/\w+[^\t\n/]*/build/src/(.*)')


def NormalizeFilePath(file_path):
  """Normalizes the file path.

  0. Strip leading "/" or "\".
  1. Convert "\", "\\", and "//" to "/"
  2. Resolve ".." and "." from the file path.
  3. Extract relative file path from the root src of a chromium repo checkout.

  eg.:
    //BUILD.gn  -> BUILD.gn
    ../a/b/c.cc -> a/b/c.cc  (os.path.normpath couldn't handle this case)
    a/b/../c.cc -> a/c.cc
    a/b/./c.cc  -> a/b/c.cc
    /b/build/slave/Android_Tests/build/src/a/b/c.cc -> a/b/c.cc
  """
  # In some log (like gn step), file paths start with // or \\, but they are
  # not an absolute path from the root directory. Thus strip them.
  file_path = file_path.lstrip('\\/')

  file_path = file_path.replace('\\', '/')
  file_path = file_path.replace('//', '/')

  filtered_parts = []

  for part in file_path.split('/'):
    if part == '..':
      if filtered_parts:
        filtered_parts.pop()
    elif part == '.':
      continue
    else:
      filtered_parts.append(part)

  file_path = '/'.join(filtered_parts)

  match = CHROMIUM_SRC_PATTERN.match(file_path)
  if match:
    file_path = match.group(1)

  return file_path


def ShouldIgnoreLine(line):
  """Returns True if the given line from failure log should be ignored.

  Some non-fatal logging messages include a file name and line number, but they
  are not related to the failure at all and could lead to false positive.
  """
  # TODO: log of ERROR level should be taken care of?
  for log_level in ('INFO:', 'WARNING:', 'ERROR:', 'VERBOSE2:'):
    if log_level in line:
      return True
  return False
