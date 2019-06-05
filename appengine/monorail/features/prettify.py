# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for source code syntax highlighting."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from third_party import ezt

from framework import framework_constants


# We only attempt to do client-side syntax highlighting on files that we
# expect to be source code in languages that we support, and that are
# reasonably sized.
MAX_PRETTIFY_LINES = 3000


def PrepareSourceLinesForHighlighting(file_contents):
  """Parse a file into lines for highlighting.

  Args:
    file_contents: string contents of the source code file.

  Returns:
    A list of _SourceLine objects, one for each line in the source file.
  """
  return [_SourceLine(num + 1, line) for num, line
          in enumerate(file_contents.splitlines())]


class _SourceLine(object):
  """Convenience class to represent one line of the source code display.

  Attributes:
      num: The line's location in the source file.
      line: String source code line to display.
  """

  def __init__(self, num, line):
    self.num = num
    self.line = line

  def __repr__(self):
    return '%d: %s' % (self.num, self.line)


def BuildPrettifyData(num_lines, path):
  """Return page data to help configure google-code-prettify.

  Args:
    num_lines: int number of lines of source code in the file.
    path: string path to the file, or just the filename.

  Returns:
    Dictionary that can be passed to EZT to render a page.
  """
  reasonable_size = num_lines < MAX_PRETTIFY_LINES

  filename_lower = path[path.rfind('/') + 1:].lower()
  ext = filename_lower[filename_lower.rfind('.') + 1:]

  # Note that '' might be a valid entry in these maps.
  prettify_class = framework_constants.PRETTIFY_CLASS_MAP.get(ext)
  if prettify_class is None:
    prettify_class = framework_constants.PRETTIFY_FILENAME_CLASS_MAP.get(
        filename_lower)
  supported_lang = prettify_class is not None

  return {
      'should_prettify': ezt.boolean(supported_lang and reasonable_size),
      'prettify_class': prettify_class,
      }
