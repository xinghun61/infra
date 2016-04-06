# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from crash.type_enums import CallStackFormatType, CallStackLanguageType


GENERATED_CODE_FILE_PATH_PATTERN = re.compile(r'out/[^/]+/gen/')


def GetFullPathForJavaFrame(function):
  """Uses java function package name to normalize and generate full file path.

  Args:
    function: Java function, for example, 'org.chromium.CrAct.onDestroy'.

  Returns:
    A string of normalized full path, for example, org/chromium/CrAct.java
  """
  return '%s.java' % '/'.join(function.split('.')[:-1])


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


def GetDepPathAndNormalizedFilePath(path, deps):
  """Determines the dep of a file path and normalizes the path.

  Args:
    path (str): Represents a path.
    deps (dict): Map dependency path to its corresponding Dependency.

  Returns:
    A tuple - (dep_path, normalized_path), dep_path is the dependency path
    of this path.  (e.g 'src/', 'src/v8/' ...etc), '' is no match found.
  """
  # First normalize the path by retreiving the normalized path.
  normalized_path = os.path.normpath(path).replace('\\', '/')

  if GENERATED_CODE_FILE_PATH_PATTERN.match(normalized_path):
    return '', normalized_path

  # Iterate through all dep paths in the parsed DEPS in an order.
  for dep_path in sorted(deps.keys(), key=lambda path: -path.count('/')):
    # We need to consider when the lowercased dep path is in the path,
    # because syzyasan build returns lowercased file path.
    dep_path_lower = dep_path.lower()

    # If this path is the part of file path, this file must be from this
    # dep.
    if dep_path in normalized_path or dep_path_lower in normalized_path:
      # Case when the retreived path is in lowercase.
      if dep_path_lower in normalized_path:
        current_dep_path = dep_path_lower
      else:
        current_dep_path = dep_path

      # Normalize the path by stripping everything off the dep's relative
      # path.
      normalized_path = normalized_path.split(current_dep_path, 1)[1]

      return (dep_path, normalized_path)

  logging.warning(
      'Failed to match dependency with file path %s' % normalized_path)
  # If the path does not match any dep, default to others.
  return '', normalized_path


def GetLanguageTypeFromFormatType(format_type):
  """Gets language type of a callstack from its format type."""
  if format_type == CallStackFormatType.JAVA:
    return CallStackLanguageType.JAVA

  return CallStackLanguageType.CPP
