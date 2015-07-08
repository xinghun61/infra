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

    in_expected_crash = False
    is_gmock_warning = False
    # Extract files and line numbers.
    for line in failure_log.splitlines():
      match = extractor_util.CPP_STACK_TRACE_FRAME_PATTERN.match(line)
      if match:
        cpp_stack_frame_index = int(match.group(1)) + 1
        if not in_expected_crash and '::CrashIntentionally()' in line:
          # TODO: Add a crash stack parser to handle crash separately.
          # TODO: Re-factor and add a list of crash signature to be ignored.
          in_expected_crash = True
      else:
        cpp_stack_frame_index = 0
        in_expected_crash = False

      if in_expected_crash or cpp_stack_frame_index > 4:
        # Ignore expected crashes and frames deep in the unexpected crashes.
        # For a crash, usually it is caused by some change to files in the top
        # frames. CLs touching other frames deep in the stacks usually are not
        # culprits. Here, we set the threshold as 4 frames.
        continue

      if 'GMOCK WARNING:' in line:
        # Ignore GMOCK WARNING statements.
        is_gmock_warning = True
        continue

      if is_gmock_warning:
        if ('You can safely ignore the above warning unless this call '
            'should not happen.') in line:
          # The end line in GMOCK WARNING statements.
          is_gmock_warning = False
        continue  # pragma: no cover


      if line and not extractor_util.ShouldIgnoreLine(line):
        self.ExtractFiles(line, signal)

    return signal


class CompileStepExtractor(Extractor):
  """For compile step, extracts files."""

  FAILURE_START_LINE_PREFIX = 'FAILED: '
  FAILURE_END_LINE_PREFIX = 'ninja: build stopped'
  NINJA_ERROR_LINE_PREFIX = 'ninja: error'

  def Extract(self, failure_log, *_):
    signal = FailureSignal()

    failure_started = False
    for line in failure_log.splitlines():
      if (not failure_started and
          line.startswith(self.FAILURE_START_LINE_PREFIX)):  # pragma: no cover
        failure_started = True
        continue
      elif failure_started and line.startswith(self.FAILURE_END_LINE_PREFIX):
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


EXTRACTORS = {
    'compile': CompileStepExtractor,
    'check_perms': CheckPermExtractor,
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
