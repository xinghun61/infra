# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from waterfall import extractor_util
from waterfall.extractor import Extractor
from waterfall.failure_signal import FailureSignal


class GeneralExtractor(Extractor):
  """A general extractor.

  It extracts file name and line numbers.
  """

  def _ExtractCppFiles(self, cpp_stacktrace_frames, signal):
    in_expected_crash = False
    for frame in cpp_stacktrace_frames:
      match = extractor_util.CPP_STACK_TRACE_FRAME_PATTERN.match(frame)
      cpp_stack_frame_index = int(match.group(1)) + 1

      if '::CrashIntentionally()' in frame:
        in_expected_crash = True

      if (not in_expected_crash and cpp_stack_frame_index <=
          extractor_util.CPP_MAXIMUM_NUMBER_STACK_FRAMES):
        self.ExtractFiles(frame, signal)

  def _ExtractPythonFiles(self, python_stacktrace_frames, signal):
    frames_with_filenames = []

    for frame in python_stacktrace_frames:
      if (extractor_util.PYTHON_STACK_TRACE_FRAME_PATTERN_1.search(frame) or
          extractor_util.PYTHON_STACK_TRACE_FRAME_PATTERN_2.search(frame)):
        frames_with_filenames.append(frame)

    for frame in frames_with_filenames[
        -extractor_util.PYTHON_MAXIMUM_NUMBER_STACK_FRAMES:]:
      self.ExtractFiles(frame, signal)

  def Extract(self, failure_log, *_):
    signal = FailureSignal()
    failure_log_lines = failure_log.splitlines()

    i = 0
    end_index = len(failure_log_lines)

    while i < end_index:
      line = failure_log_lines[i]
      cpp_stacktrace_match = extractor_util.CPP_STACK_TRACE_FRAME_PATTERN.match(
          line)
      if cpp_stacktrace_match:
        # Handle cpp failure stacktraces.
        start = i
        for line in failure_log_lines[start:]:  # pragma: no cover
          if extractor_util.CPP_STACK_TRACE_FRAME_PATTERN.match(line):
            i += 1
          else:
            break
        end = i
        cpp_stacktrace_frames = failure_log_lines[start:end]
        self._ExtractCppFiles(cpp_stacktrace_frames, signal)
      elif extractor_util.PYTHON_STACK_TRACE_START_PATTERN.search(line):
        # Handle python failure stacktraces.
        i += 1
        start = i
        while i < end_index:  # pragma: no cover
          line = failure_log_lines[i]
          if (extractor_util.PYTHON_STACK_TRACE_FRAME_PATTERN_1.search(line) or
              extractor_util.PYTHON_STACK_TRACE_FRAME_PATTERN_2.search(line)):
            i += 2
          else:
            break
        end = i
        python_stacktrace_frames = failure_log_lines[start:end]
        self._ExtractPythonFiles(python_stacktrace_frames, signal)
      elif 'GMOCK WARNING' in line:
        # Ignore GMOCK WARNING statements.
        start = i
        for l in failure_log_lines[start:]:  # pragma: no cover
          if ('You can safely ignore the above warning unless this call '
              'should not happen.') in l:
            # The end line in GMOCK WARNING statements.
            break
          i += 1
      else:
        if line and not extractor_util.ShouldIgnoreLine(line):
          self.ExtractFiles(line, signal)

      i += 1

    return signal


class CompileStepExtractor(Extractor):
  """For compile step, extracts files."""

  FAILURE_START_LINE_PREFIX = 'FAILED: '
  NINJA_FAILURE_END_LINE_PREFIX = 'ninja: build stopped'
  NINJA_ERROR_LINE_PREFIX = 'ninja: error'
  ERROR_LINE_END_PATTERN = re.compile(
      '^\d+ errors? generated.')
  IOS_ERROR_LINE_START_PREFIX = 'CompileC'

  IOS_BUILDER_NAMES_FOR_COMPILE = ['iOS_Simulator_(dbg)', 'iOS_Device']
  MAC_MASTER_NAME_FOR_COMPILE = 'chromium.mac'

  def Extract(self, failure_log, test_name, step_name, bot_name, master_name):
    signal = FailureSignal()

    failure_started = False
    if (master_name == self.MAC_MASTER_NAME_FOR_COMPILE and
        bot_name in self.IOS_BUILDER_NAMES_FOR_COMPILE):
      error_lines = []
      for line in reversed(failure_log.splitlines()):
        if (not failure_started and
            self.ERROR_LINE_END_PATTERN.match(line)):
          failure_started = True
          continue

        if failure_started:
          if line.startswith(self.IOS_ERROR_LINE_START_PREFIX):
            failure_started = False
            for l in error_lines[:-4]:
              self.ExtractFiles(l, signal)
            error_lines = []
          else:
            error_lines.append(line)

    else:
      for line in failure_log.splitlines():
        if line.startswith(self.FAILURE_START_LINE_PREFIX):
          if not failure_started:
            failure_started = True
          continue  # pragma: no cover
        elif failure_started and self.ERROR_LINE_END_PATTERN.match(line):
          failure_started = False
        elif failure_started and line.startswith(
            self.NINJA_FAILURE_END_LINE_PREFIX):  # pragma: no cover
          break

        if failure_started or line.startswith(self.NINJA_ERROR_LINE_PREFIX):
          # either within the compile errors or is a ninja error.
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


class CheckSizesExtractor(Extractor):
  """For Sizes, only extract files."""
  BEGINNING_MARKER = '# Static initializers in'
  HINT_MARKER = '# HINT:'
  END_MARKER = re.compile('# Found \\d+ static initializers in \\d+ files?\\.')

  def Extract(self, failure_log, *_):
    signal = FailureSignal()
    failure_started = False

    for line in failure_log.splitlines():
      if line.startswith(self.BEGINNING_MARKER):
        failure_started = True
        continue

      # Skip hints.
      if line.startswith(self.HINT_MARKER):
        continue

      if self.END_MARKER.match(line):
        failure_started = False
        continue

      # Begin extracting file names.
      if failure_started:
        self.ExtractFiles(line, signal)

    return signal


EXTRACTORS = {
    'compile': CompileStepExtractor,
    'check_perms': CheckPermExtractor,
    'sizes': CheckSizesExtractor,
}


def ExtractSignal(master_name, bot_name, step_name, test_name, failure_log):
  """Uses an appropriate extractor to extract failure signals.

  Returns:
    A FailureSignal.
  """
  # Fall back to a general-but-maybe-not-accurate extractor.
  extractor_class = EXTRACTORS.get(step_name, GeneralExtractor)
  return extractor_class().Extract(
      failure_log, test_name, step_name, bot_name, master_name)
