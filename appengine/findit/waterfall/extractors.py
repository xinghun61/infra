# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from waterfall.extractor import Extractor
from waterfall import extractor_util
from waterfall.failure_signal import FailureSignal


class GeneralExtractor(Extractor):
  """A general extractor.

  It extracts file name and line numbers.
  """

  def Extract(self, failure_log, *_):
    signal = FailureSignal()

    # Extract files and line numbers.
    for line in failure_log.splitlines():
      if line and not extractor_util.ShouldIgnoreLine(line):
        self.ExtractFiles(line, signal)

    return signal


class CompileStepExtractor(Extractor):
  """For compile step, extracts files."""

  FAILURE_START_LINE_PREFIX = 'FAILED: '
  FAILURE_END_LINE_PREFIX = 'ninja: build stopped'

  def Extract(self, failure_log, *_):
    signal = FailureSignal()

    failure_started = False
    for line in failure_log.splitlines():
      if (not failure_started and
          line.startswith(self.FAILURE_START_LINE_PREFIX)):  # pragma: no cover
        failure_started = True
      elif failure_started and line.startswith(self.FAILURE_END_LINE_PREFIX):
        break

      if failure_started:
        self.ExtractFiles(line, signal)

    return signal


class CheckPermExtractor(Extractor):
  """For CheckPerm, only extracts files."""

  def Extract(self, failure_log, *_):
    signal = FailureSignal()

    for line in reversed(failure_log.splitlines()):
      if line.startswith('FAILED'):  # pragma: no cover
        # This is where the failure message starts.
        # As we do reverse check, we should stop here.
        break

      # Extract files.
      for match in extractor_util.FILE_PATH_LINE_PATTERN.finditer(line):
        file_path, line_number = match.groups()
        signal.AddFile(extractor_util.NormalizeFilePath(file_path),
                       line_number)

    return signal


EXTRACTORS = {
    'compile': CompileStepExtractor,
    'gn': CompileStepExtractor,
    'check_perms': CheckPermExtractor,
}


def ExtractSignal(master_name, bot_name, step_name, test_name, failure_log):
  # Fall back to a general-but-maybe-not-accurate extractor.
  extractor_class = EXTRACTORS.get(step_name, GeneralExtractor)
  return extractor_class().Extract(
      master_name, bot_name, step_name, test_name, failure_log)
