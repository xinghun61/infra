#!/usr/bin/python
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This script provides utility functions to parse unified diff.

This file here is copy-pasted from:
https://chromium.googlesource.com/chromium/tools/build/+/refs/heads/master/scripts/slave/recipe_modules/code_coverage/resources/diff_util.py.
Do NOT modify this file directly, instead, modify it at recipe side first and
if it stick, copy past to here.

This file is NOT meant to change often, if you need to add something, please
consider other places first.
"""

from collections import defaultdict
import logging
import re

# Identifies diff section header, which has the following format:
# @@ -{old_start_line},{old_length} +{new_start_line},{new_length} @@
# For example: '@@ -2,8 +2,8 @@'
_DIFF_RANGE_HEADER_PREFIX = '@@'
_DIFF_RANGE_HEADER_REGEX = re.compile(r'^@@ \-(\d+),?(\d+)? \+(\d+),?(\d+)? @@')

# Identifies the line representing the info of the from file.
# For example: '--- file1.txt 2019-02-02 17:51:49.000000000 -0800'
_DIFF_FROM_FILE_PREFIX = '---'

# Identifies the line representing the info of the to file.
# For example: '+++ file.txt 2019-02-02 17:51:49.000000000 -0800'
_DIFF_TO_FILE_PREFIX = '+++'

# Identifies different lines deleted from the first file.
# For example: '-if (num >= 0) {'
_DIFF_MINUS_LINE_PREFIX = '-'

# Identifies different lines added to the the second file.
# For example: '+if (num >= 0) {'
_DIFF_PLUS_LINE_PREFIX = '+'

# Identifies unchanged line between the two files.
# For example: ' int num = 1;'
_DIFF_WHITESPACE_LINE_PREFIX = ' '


def parse_added_line_num_from_unified_diff(diff_lines):
  """Parses the unified diff output and returns the line number of added lines.

  Note that this method *only* cares about the added lines, and the main use
  case is to figure out incremental coverage percentage of newly added lines by
  the patch.

  Args:
    diff_lines (list of str): Unified diff.

  Returns:
    A dictionary whose key is a file name that is relative to the source root,
    and the corresponding value a set of line numbers.
  """
  file_to_added_lines = defaultdict(set)

  current_file = None
  current_base_line_num = None
  current_offset = None

  for line in diff_lines:
    # E.g. '+++ dev/null'
    if line.startswith('+++ /dev/null'):
      current_file = None
      current_base_line_num = None
      current_offset = None
      continue

    # E.g. '+++ b/test_file.txt'
    if line.startswith('+++ b/'):
      current_file = line[len('+++ b/'):]
      current_base_line_num = None
      current_offset = None
      continue

    if current_file is None:
      # If a file is deleted, there should be no added lines in the diff ranges.
      continue

    # E.g. '@@ -1,3 +1,3 @@''
    if line.startswith(_DIFF_RANGE_HEADER_PREFIX):
      matched = _DIFF_RANGE_HEADER_REGEX.match(line)
      if not matched:
        raise RuntimeError(
            'This script doesn\'t understand the diff section header: "%s".' %
            line)

      current_base_line_num = int(matched.group(3))
      current_offset = 0
      continue

    # E.g. ' unchanged line' and '\n'.
    is_unchanged_line = line.startswith(' ') or line == ''
    if is_unchanged_line and current_base_line_num is not None:
      current_offset += 1
      continue

    # E.g. '+made some change to this line'
    is_new_line = line.startswith('+')
    if is_new_line and current_base_line_num is not None:
      line_num = current_base_line_num + current_offset
      file_to_added_lines[current_file].add(line_num)
      current_offset += 1

  return file_to_added_lines


def generate_line_number_mapping(diff_lines, from_file_lines, to_file_lines):
  """Generates a mapping of unchanged lines between two files.

  Args:
    diff_lines (list of str): Unified diff.
    from_file_lines (list of str): File content of one file.
    to_file_lines (list of str): File content of the other file.

  Returns:
    A dict that maps line numbers of unchanged lines from one file to the other.
  """
  logging.info('The diff content:\n%s', '\n'.join(diff_lines))
  logging.info('-' * 80)

  # In the diff output, line number starts from 1, so manually inserts a line
  # to the beginging to simply later index related computations.
  from_file_lines = from_file_lines[:]
  to_file_lines = to_file_lines[:]
  from_file_lines.insert(0, 'Manually padded line')
  to_file_lines.insert(0, 'Manually padded line')

  def _verify_and_add_unchanged_line(from_file_line_num, from_file_lines,
                                     to_file_line_num, to_file_lines,
                                     line_num_mapping):
    from_file_line = from_file_lines[from_file_line_num]
    to_file_line = to_file_lines[to_file_line_num]
    assert from_file_line == to_file_line, (
        'Unexpected line difference between %s and %s' % (from_file_line,
                                                          to_file_line))
    line_num_mapping[from_file_line_num] = (to_file_line_num, to_file_line)

  line_num_mapping = {}
  from_file_line_num = 0
  to_file_line_num = 0
  for line in diff_lines:
    # E.g. '--- file1.txt 2019-02-02 17:51:49.000000000 -0800'
    if line.startswith(_DIFF_FROM_FILE_PREFIX) or line.startswith(
        _DIFF_TO_FILE_PREFIX):
      continue

    # E.g. '@@ -1,3 +1,3 @@''
    if line.startswith(_DIFF_RANGE_HEADER_PREFIX):
      matched = _DIFF_RANGE_HEADER_REGEX.match(line)
      if not matched:
        raise RuntimeError(
            'This script doesn\'t understand the diff section header: "%s".' %
            line)

      from_file_diff_section_line_num = int(matched.group(1))
      to_file_diff_section_line_num = int(matched.group(3))
      assert (from_file_diff_section_line_num -
              from_file_line_num == to_file_diff_section_line_num -
              to_file_line_num), 'Inconsistent number of unchanged lines'
      while from_file_line_num < from_file_diff_section_line_num:
        _verify_and_add_unchanged_line(from_file_line_num, from_file_lines,
                                       to_file_line_num, to_file_lines,
                                       line_num_mapping)
        from_file_line_num += 1
        to_file_line_num += 1

      continue

    # E.g. ' unchanged line'.
    if line.startswith(_DIFF_WHITESPACE_LINE_PREFIX):
      _verify_and_add_unchanged_line(from_file_line_num, from_file_lines,
                                     to_file_line_num, to_file_lines,
                                     line_num_mapping)
      from_file_line_num += 1
      to_file_line_num += 1
      continue

    # E.g. '-extra line in the from file'
    if line.startswith(_DIFF_MINUS_LINE_PREFIX):
      from_file_line_num += 1
      continue

    # E.g. '+extra line in the to file'
    if line.startswith(_DIFF_PLUS_LINE_PREFIX):
      to_file_line_num += 1
      continue

  assert (len(from_file_lines) - from_file_line_num == len(to_file_lines) -
          to_file_line_num
         ), 'Inconsistent number of unchanged lines at the end of the files'
  while from_file_line_num < len(from_file_lines):
    _verify_and_add_unchanged_line(from_file_line_num, from_file_lines,
                                   to_file_line_num, to_file_lines,
                                   line_num_mapping)
    from_file_line_num += 1
    to_file_line_num += 1

  assert 0 in line_num_mapping and line_num_mapping[0] == (
      0, 'Manually padded line'), 'A manually padded line is expected to exist'
  del line_num_mapping[0]
  return line_num_mapping
