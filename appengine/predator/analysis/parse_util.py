# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from analysis.constants import CHROMIUM_REPO_URL
from analysis.constants import CHROMIUM_ROOT_PATH

GENERATED_CODE_FILE_PATH_PATTERN = re.compile(r'.*out/[^/]+/gen/')
THIRD_PARTY_FILE_PATH_MARKER = 'third_party'

JAVA_CHROMIUM_FUNCTION_MARKER = 'org.chromium.chrome.browser'
JAVA_CHROMIUM_CODE_REPOSITORY_PATH = 'src/chrome/android/java/src'


def GetFullPathForJavaFrame(function):
  """Uses java function package name to normalize and generate full file path.

  Args:
    function: Java function, for example, 'org.chromium.CrAct.onDestroy'.

  Returns:
    A string of normalized full path, for example, org/chromium/CrAct.java
  """
  file_path = '%s.java' % '/'.join(function.split('.')[:-1])
  if JAVA_CHROMIUM_FUNCTION_MARKER in function:
    file_path = '%s/%s' % (JAVA_CHROMIUM_CODE_REPOSITORY_PATH, file_path)

  return file_path


def GetCrashedLineRange(line_range_str):
  """Gets crashed line range.

  Args:
    line_range_str (str): Has the format of 'line_number:range' if crash line
      range provided, else 'line_number'.

  Returns:
    A list of line numbers (int) where crash happened. For example, 655:1 has
    crashed lines 655 and 656.
  """
  if ':' not in line_range_str:
    return [int(line_range_str)]

  line_number, range_length = map(int, line_range_str.split(':'))

  return range(line_number, line_number + range_length + 1)


def GetDepPathAndNormalizedFilePath(path, deps, is_java=False,
                                    root_path=None,
                                    root_repo_url=None):
  """Determines the dep of a file path and normalizes the path.

  Args:
    path (str): Represents a path.
    deps (dict): Map dependency path to its corresponding Dependency.
    is_java (boolean): If the path is a java stack path.

  Returns:
    A tuple - (dep_path, normalized_path, repo_url)
    dep_path (str): Dependency path of this path.  (e.g 'src', 'src/v8'
      ...etc), '' is no match found.
    normalized_path (str): Normalized relative file path starting from dep_path.
    repo_url (str): Repository url corresponding to dep_path.
  """
  # Default the root repo to chromium if None provided.
  root_path = root_path or CHROMIUM_ROOT_PATH
  root_repo_url = root_repo_url or CHROMIUM_REPO_URL
  # First normalize the path by retrieving the normalized path.
  normalized_path = os.path.normpath(path).replace('\\', '/')

  if GENERATED_CODE_FILE_PATH_PATTERN.match(normalized_path):
    logging.info('Generated code path %s', normalized_path)
    return '', normalized_path, None

  # Iterate through all dep paths in the parsed DEPS in an order.
  for dep_path in sorted(deps.keys(), key=lambda path: -path.count('/')):
    # trim the 'src' in the beginning of the dep_path to match, because there
    # are many cases, especially in linux platform, the file paths are like,
    # 'third_party/WebKit/Source/...', or 'v8/...'.
    trimmed_dep_path = dep_path
    if (trimmed_dep_path.startswith(root_path + '/') and
        trimmed_dep_path != root_path):
      trimmed_dep_path = trimmed_dep_path[len(root_path + '/'):]

    # We need to consider when the lowercased dep path is in the path,
    # because syzyasan builds and win canary crashes return lowercased file
    # path.
    trimmed_dep_path_lower = trimmed_dep_path.lower()
    dep_path_lower = dep_path.lower()

    current_dep_path = ''

    if (normalized_path.startswith(trimmed_dep_path) or
        normalized_path.startswith(trimmed_dep_path_lower)):
      # Case when the retrieved path is in lowercase.
      if normalized_path.startswith(trimmed_dep_path):
        current_dep_path = trimmed_dep_path
      else:
        current_dep_path = trimmed_dep_path_lower

    # For some special cases, for example, a file like
    # 'https://chromium.googlesource.com/chromium/src/+/master/'
    # 'third_party/tcmalloc/chromium/src/common.cc', this path shouldn't be
    # matched with 'src' in between, it should be matched to the trimmed 'src'
    # in the beginning.
    if (not normalized_path.startswith(THIRD_PARTY_FILE_PATH_MARKER) and
        (dep_path + '/' in normalized_path or
         dep_path_lower + '/' in normalized_path)):
      if dep_path in normalized_path:
        current_dep_path = dep_path
      else:
        current_dep_path = dep_path_lower

    # Normalize the path by stripping everything off the dep's relative
    # path.
    if current_dep_path:
      normalized_path = normalized_path.split(current_dep_path + '/', 1)[1]
      return dep_path, normalized_path, deps[dep_path].repo_url

  # If path is a java stack path, don't default dep_path to src.
  if is_java:
    return '', normalized_path, None

  # For some crashes, the file path looks like this:
  # third_party/WebKit/Source/a.cc, the src in the beginning is trimmed, so
  # default the dep path to 'src' if no match found.
  return root_path, normalized_path, root_repo_url
