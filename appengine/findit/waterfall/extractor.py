# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from waterfall import extractor_util


class Extractor(object):
  """An interface to extract failure signal from a failed step or test."""

  def ExtractFiles(self, message_line, failure_signal):
    """Extracts files from given message line into ``failure_signal``."""
    match = (
        extractor_util.PYTHON_STACK_TRACE_FRAME_PATTERN_1.search(message_line)
        or
        extractor_util.PYTHON_STACK_TRACE_FRAME_PATTERN_2.search(message_line))
    if match:
      trace_line = match.groupdict()
      failure_signal.AddFile(
          extractor_util.NormalizeFilePath(trace_line['file']),
          trace_line['line'])
    else:
      for match in extractor_util.FILE_PATH_LINE_PATTERN.finditer(message_line):
        file_path, line_number = match.groups()
        failure_signal.AddFile(extractor_util.NormalizeFilePath(file_path),
                               line_number)

  # pylint disable=W0613, R0201
  def Extract(self, failure_log, test_name, step_name, bot_name, master_name):
    """Analyzes ``failure_log``, extracts and returns a FailureSignal."""
    raise NotImplementedError()
