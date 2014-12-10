# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parser of memory suppressions output."""

import logging
import re


# Version number of the parser. Cached results will be re-parsed
# when this changes.
VERSION = 3


START_RE = re.compile(r'Suppressions used:')
END_RE = re.compile(r'-+')
SUPPRESSION_RE = re.compile(r'\s*[^\s]* (.*)')
SUPPRESSION_RE2 = re.compile(r'\s*[^\s]*\s*[^\s]*\s*[^\s]* (.*)')

def parse(log_contents):
  """Return a list of used suppression names."""
  suppression_names = []
  suppression_block = False
  suppression_regex = None
  for line in log_contents:
    start_match = START_RE.match(line)
    end_match = END_RE.match(line)
    if not suppression_block and start_match:
      suppression_block = True
      suppression_regex = None
    elif suppression_block and end_match:
      suppression_block = False
      suppression_regex = None
    elif suppression_block:
      if not suppression_regex:
        if ('count' in line and 'bytes' in line and
            'objects' in line and 'name' in line):
          suppression_regex = SUPPRESSION_RE2
        elif ('count' in line and 'name' in line):
          suppression_regex = SUPPRESSION_RE
        else:  # pragma: no cover
          logging.error('Cannot recognize suppression format: <<<%s>>>' % line)
        continue  # pragma: no cover
      suppression_match = suppression_regex.match(line)
      if suppression_match:
        name = suppression_match.group(1).strip()
        if name not in suppression_names:
          suppression_names.append(name)
      elif line.strip():  # pragma: no cover
        # Only signal errors for non-empty lines.
        logging.error('Unmatched suppression line: <<<%s>>>' % line)
  return suppression_names
