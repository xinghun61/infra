# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides functions for file path related operations.

It has functions to:
  * Check if two files are the same.
  * Check if two files are related.
"""

import os
import re


_COMMON_SUFFIXES = [
    'impl',
    'browser_tests',
    'browser_test',
    'browsertest',
    'browsertests',
    'unittests',
    'unittest',
    'tests',
    'test',
    'gcc',
    'msvc',
    'arm',
    'arm64',
    'mips',
    'portable',
    'x86',
    'android',
    'ios',
    'linux',
    'mac',
    'ozone',
    'posix',
    'win',
    'aura',
    'x',
    'x11',
]

_COMMON_TEST_SUFFIXES = [
    'browser_tests',
    'browser_test',
    'browsertest',
    'browsertests',
    'unittests',
    'unittest',
    'tests',
    'test',
]

_COMMON_SUFFIX_PATTERNS = [
    re.compile('.*(_%s)$' % suffix) for suffix in _COMMON_SUFFIXES
]

_COMMON_TEST_SUFFIX_PATTERNS = [
    re.compile('.*(_%s)$' % suffix) for suffix in _COMMON_TEST_SUFFIXES
]

_RELATED_FILETYPES = [['h', 'hh'
                       'c', 'cc', 'cpp', 'm', 'mm', 'o', 'obj'], ['py', 'pyc'],
                      ['gyp', 'gypi']]


def IsSameFile(changed_src_file_path, file_path_in_log):
  """Guesses if the two files are the same.

  Args:
    changed_src_file_path (str): Full path of a file committed to git repo.
    file_path_in_log (str): Path of a file appearing in a failure log. It might
        not be a full path.

  Returns:
    True if the two files are likely the same, otherwise False. Eg.:
      True: (chrome/test/base/chrome_process_util.h, base/chrome_process_util.h)
      True: (a/b/x.cc, a/b/x.cc)
      False: (c/x.cc, a/b/c/x.cc)
  """
  changed_src_file_path_lower = changed_src_file_path.lower()
  file_path_in_log_lower = file_path_in_log.lower()

  if changed_src_file_path_lower == file_path_in_log_lower:
    return True
  return changed_src_file_path_lower.endswith('/%s' % file_path_in_log_lower)


def _NormalizeObjectFilePath(file_path):
  """Normalize the file path to an c/c++ object file.

  During compile, a/b/c/file.cc in TARGET will be compiled into object file
  obj/a/b/c/TARGET.file.o, thus 'obj/' and TARGET need to be removed from path.

  Args:
    file_path (str): A path to an object file (.o or .obj) after compile.
  Returns:
    A normalized file path.
  """
  if file_path.startswith('obj/'):
    file_path = file_path[4:]
  file_dir = os.path.dirname(file_path)
  file_name = os.path.basename(file_path)
  parts = file_name.split('.', 1)
  if len(parts) == 2 and (parts[1].endswith('.o') or parts[1].endswith('.obj')):
    object_file = parts[1]
    name = os.path.splitext(object_file)[0]
    # Special case for file.cc.obj and similar cases.
    if name not in ['c', 'cc', 'cpp', 'm', 'mm']:
      file_name = parts[1]

  if file_dir:
    return '%s/%s' % (file_dir, file_name)
  else:
    return file_name


def _AreBothFilesTestRelated(changed_src_file_path, file_in_log_path):
  """Tests if both file names contain test-related suffixes."""
  changed_file_name = os.path.splitext(
      os.path.basename(changed_src_file_path))[0]
  file_in_log_name = os.path.splitext(os.path.basename(file_in_log_path))[0]

  is_changed_file_test_related = False
  is_file_in_log_test_related = False

  for test_suffix_patten in _COMMON_TEST_SUFFIX_PATTERNS:
    if test_suffix_patten.match(changed_file_name):
      is_changed_file_test_related = True
    if test_suffix_patten.match(file_in_log_name):
      is_file_in_log_test_related = True

  return is_changed_file_test_related and is_file_in_log_test_related


def _StripExtensionAndCommonSuffix(file_path):
  """Strips extension and common suffixes from file name to guess relation.

  Examples:
    file_impl.cc, file_unittest.cc, file_impl_mac.h -> file
  """
  file_dir = os.path.dirname(file_path)
  file_name = os.path.splitext(os.path.basename(file_path))[0]
  while True:
    match = None
    for suffix_patten in _COMMON_SUFFIX_PATTERNS:
      match = suffix_patten.match(file_name)
      if match:
        file_name = file_name[:-len(match.group(1))]
        break

    if not match:
      break

  return os.path.join(file_dir, file_name).replace(os.sep, '/')


def _GetRelatedExtensionsList(extension):
  for related_filetype_list in _RELATED_FILETYPES:
    if extension in related_filetype_list:
      return related_filetype_list
  return []


def IsRelated(changed_src_file_path, file_path):
  """Checks if two files are related.

  Example of related files:
    1. file.h <-> file_impl.cc
    2. file_impl.cc <-> file_unittest.cc
    3. file_win.cc <-> file_mac.cc
    4. x.h <-> x.cc

  Example of not related files:
    1. a_tests.py <-> a_browsertests.py
    2. a.isolate <-> a.cc
    3. a.py <-> a.cpp
  """
  changed_src_file_extension = os.path.splitext(changed_src_file_path)[1][1:]
  file_path_extension = os.path.splitext(file_path)[1][1:]

  if file_path_extension not in _GetRelatedExtensionsList(
      changed_src_file_extension):
    return False

  if file_path.endswith('.o') or file_path.endswith('.obj'):
    file_path = _NormalizeObjectFilePath(file_path)

  if _AreBothFilesTestRelated(changed_src_file_path, file_path):
    return False

  if IsSameFile(
      _StripExtensionAndCommonSuffix(changed_src_file_path),
      _StripExtensionAndCommonSuffix(file_path)):
    return True

  return False


def StripChromiumRootDirectory(file_path):
  # Strip src/ from file path to make all files relative to the chromium root
  # directory.
  if file_path.startswith('src/'):
    file_path = file_path[4:]
  return file_path