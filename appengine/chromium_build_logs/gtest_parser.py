# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parser of gtest (googletest) output."""

import bisect
import logging
import re


# Version number of the parser. Cached results will be re-parsed
# when this changes.
VERSION = 7


# These regular expressions detect start and end of each test case run.
START_RE = re.compile(r'^\[ RUN      \] ([^\s.]+)\.([^\s.]+)\r?$',
                      re.MULTILINE)
END_RE = re.compile(r'^\[  (     OK|FAILED ) \] ([^\s.]+)\.([^\s.]+)' +
                    '(?:, where TypeParam = .* and GetParam\(\) = .*)?' +
                    ' \((\d+) ms\)\r*$', re.MULTILINE)


LOG_LINE_LENGTH_LIMIT = 120
LOG_LINES_LIMIT = 50
LOG_TRIMMED_MESSAGE = ['', '(trimmed by parser)', '']
LOG_LINE_TRUNCATED_MESSAGE = ' (truncated by parser)'


def trim_long_log(text):
  lines = text.splitlines()
  for i in range(len(lines)):
    if len(lines[i]) > LOG_LINE_LENGTH_LIMIT:
      lines[i] = lines[i][:LOG_LINE_LENGTH_LIMIT] + LOG_LINE_TRUNCATED_MESSAGE
  if len(lines) < LOG_LINES_LIMIT:
    return '\n'.join(lines)
  half_length = (LOG_LINES_LIMIT - len(LOG_TRIMMED_MESSAGE)) / 2
  return '\n'.join(lines[:half_length] +
                   LOG_TRIMMED_MESSAGE +
                   lines[-half_length:])


def extract_test_prefix(raw_fullname):
  """Returns a (prefix, fullname) tuple corresponding to raw_fullname."""

  fullname = raw_fullname.replace('FLAKY_', '').replace('FAILS_', '')

  test_prefix = ''
  if 'FLAKY_' in raw_fullname:
    test_prefix = 'FLAKY'
  elif 'FAILS_' in raw_fullname:  # pragma: no cover
    test_prefix = 'FAILS'

  return (test_prefix, fullname)

def parse(log_contents):
  """
  Return a list of dictionaries, one for each test case, representing
  parsed data we are interested in.
  """

  tests_dict = {}

  for match in END_RE.finditer(log_contents):
    result = match.group(1).strip()
    raw_fullname = (match.group(2) + '.' + match.group(3)).strip()
    test_prefix, fullname = extract_test_prefix(raw_fullname)
    run_time_ms = int(match.group(4))

    if fullname in tests_dict: # pragma: no cover
      logging.warn('Test appears multiple times in a log: ' + fullname)
      continue

    tests_dict[fullname] = {
      'is_successful': 'OK' in result,
      'is_crash_or_hang': False,
      'test_prefix': test_prefix,
      'run_time_ms': run_time_ms,
      'end_match_start_pos': match.start()
    }

  start_match_start_pos_list = []

  for match in START_RE.finditer(log_contents):
    raw_fullname = (match.group(1) + '.' + match.group(2)).strip()
    test_prefix, fullname = extract_test_prefix(raw_fullname)

    if fullname in tests_dict:
      # Good match, update the match positions.
      tests_dict[fullname]['start_match_start_pos'] = match.start()
      tests_dict[fullname]['start_match_end_pos'] = match.end()
    if fullname not in tests_dict:
      tests_dict[fullname] = {
        'is_successful': False,
        'is_crash_or_hang': True,
        'test_prefix': test_prefix,
        'run_time_ms': -1,
        'start_match_start_pos': match.start(),
        'start_match_end_pos': match.end()
      }
    start_match_start_pos_list.append(
        tests_dict[fullname]['start_match_start_pos'])

  start_match_start_pos_list.sort()

  for fullname in tests_dict:
    cur_dict = tests_dict[fullname]

    cur_dict['log'] = ''
    if 'start_match_end_pos' in cur_dict and 'end_match_start_pos' in cur_dict:
      # Easy case, just extract part between start match end position
      # and end match start position.
      cur_dict['log'] = log_contents[
          cur_dict['start_match_end_pos']:cur_dict['end_match_start_pos']]
    elif cur_dict['is_crash_or_hang']:
      # We need to find the start position of the _next_ start match,
      # if there is one. Otherwise just take everything up to end of the log.
      start_match_start_pos_index = bisect.bisect_right(
          start_match_start_pos_list, cur_dict['start_match_end_pos'])
      if start_match_start_pos_index == len(start_match_start_pos_list):
        start_match_start_pos = -1
      else:
        start_match_start_pos = \
            start_match_start_pos_list[start_match_start_pos_index]
      cur_dict['log'] = log_contents[
          cur_dict['start_match_end_pos']:start_match_start_pos]

    cur_dict['log'] = trim_long_log(cur_dict['log']).strip()

    # Remove our internal data from returned dict.
    if 'start_match_start_pos' in cur_dict:
      del cur_dict['start_match_start_pos']
    if 'start_match_end_pos' in cur_dict:
      del cur_dict['start_match_end_pos']
    if 'end_match_start_pos' in cur_dict:
      del cur_dict['end_match_start_pos']

  return tests_dict
