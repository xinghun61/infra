# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from waterfall import extractor_util
from waterfall.extractor import Extractor
from waterfall.failure_signal import FailureSignal


class GeneralExtractor(Extractor):
  """A general extractor.

  It extracts file name and line numbers.
  """
  INDIRECT_LEAK_MARKER_PATTERN = re.compile(
      r'.*Indirect leak of \d+ byte\(s\) in \d+ object\(s\) allocated from:.*')

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

        if (start >= 1 and
            self.INDIRECT_LEAK_MARKER_PATTERN.match(
                failure_log_lines[start - 1])):
          # Ignore stack trace of an indirect leak.
          continue

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
  """For compile step, extracts files and identifies failed targets."""
  FAILURE_START_LINE_PREFIX = 'FAILED: '
  FAILURE_WITH_ERROR_PATTERN = re.compile(r'FAILED with \d+:')
  LINUX_FAILED_SOURCE_TARGET_PATTERN = re.compile(
      r'(?:-c ([^\s-]+))? -o ([^\s-]+)')
  WINDOWS_FAILED_SOURCE_TARGET_PATTERN = re.compile(
      r'/c ([^\s-]+)\s+/Fo([^\s-]+)')
  WINDOWS_LINK_FAILURE_PATTERN = re.compile(r'/OUT:([^\s-]+)')

  NINJA_FAILURE_END_LINE_PREFIX = 'ninja: build stopped'
  NINJA_ERROR_LINE_PREFIX = 'ninja: error'
  ERROR_LINE_END_PATTERN = re.compile(r'^\d+ errors? generated.')
  IOS_ERROR_LINE_START_PREFIX = 'CompileC'

  IOS_BUILDER_NAMES_FOR_COMPILE = ['iOS_Simulator_(dbg)', 'iOS_Device']
  MAC_MASTER_NAME_FOR_COMPILE = 'chromium.mac'

  def GetFailedTarget(self, line, signal):
    match = self.LINUX_FAILED_SOURCE_TARGET_PATTERN.search(line)

    if match:
      # Try parsing the failure line as a linux build.
      source_file = match.group(1)
      target = match.group(2)

      if source_file:
        # Failure is a compile failure.
        signal.AddTarget({
            'target': target,
            'source': source_file
        })
      else:
        # Failure is a linker error.
        signal.AddTarget({
            'target': target
        })
    else:
      # If no match was found using Linux pattern matching, fallback to Windows.
      match = self.WINDOWS_FAILED_SOURCE_TARGET_PATTERN.search(line)

      if match:
        # Failure is a compile failure.
        source_file = match.group(1)
        object_file = match.group(2)
        signal.AddTarget({
            'target': object_file,
            'source': source_file
        })
      else:
        match = self.WINDOWS_LINK_FAILURE_PATTERN.search(line)
        if match:
          # Failure is a linker error.
          target = match.group(1)
          signal.AddTarget({'target': target})

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
          self.GetFailedTarget(line, signal)
          if not failure_started:
            failure_started = True
          continue  # pragma: no cover
        elif self.FAILURE_WITH_ERROR_PATTERN.match(line):
          # It is possible the target and source file associated with a compile
          # failure is logged outside a 'FAILED: ... 1 error generated' block,
          # so extract regardless of failure_started.
          self.GetFailedTarget(line, signal)
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


class AndroidJavaTestExtractor(Extractor):
  """An extractor for java-based Android tests.

    Note this extractor should not be used directly, but contains shared
    constants and functions to be used by its children classes.
  """
  # White-list of java packages to consider.
  JAVA_PACKAGES_TO_CONSIDER = ['org.chromium.']

  JAVA_TEST_NAME_PATTERN = re.compile(
      r'((?P<package_classname>(?:\w+(?:\$\w+)?\.)+)(?P<method><?\w+>?))')

  JAVA_STACK_TRACE_START_MARKERS = ['Caused by:']

  def _IsStartOfStackTrace(self, line):
    for start_marker in self.JAVA_STACK_TRACE_START_MARKERS:
      if line.startswith(start_marker):
        return True
    return False

  def _InWhitelist(self, package_filename):
    if package_filename:  # pragma: no cover
      for package in self.JAVA_PACKAGES_TO_CONSIDER:
        if package_filename.startswith(package):
          return True
    return False

  def ExtractJavaFileMatch(self, match, signal):
    match_dict = match.groupdict()
    package_classname = match_dict.get('package_classname')
    filename = match_dict.get('filename')
    line_number = match_dict.get('line_number')

    if self._InWhitelist(package_classname):
      if filename:
        file_path = os.path.join(
            '/'.join(package_classname.split('.')[:-2]), filename)
      else:
        file_path = '/'.join(package_classname.split('.')[:-1]) + '.java'
      signal.AddFile(extractor_util.NormalizeFilePath(file_path), line_number)

  def Extract(self, failure_log, *_):
    raise NotImplementedError(
        'Extract should be implemented in the child class.')  # pragma: no cover


class InstrumentationTestExtractor(AndroidJavaTestExtractor):
  """For Instrumentation tests."""
  # Beginning marker for Java stack trace.
  JAVA_STACK_TRACE_BEGINNING_MARKER = re.compile(r'^.*\[FAIL] .*\#.*:')

  def Extract(self, failure_log, *_):
    signal = FailureSignal()
    failure_started = False
    in_failure_stacktrace_within_range = False
    java_stack_frame_index = 0

    for line in failure_log.splitlines():  # pragma: no cover
      if not failure_started and line.endswith('Detailed Logs'):
        failure_started = True
        continue

      if failure_started:
        if (not in_failure_stacktrace_within_range and
            self.JAVA_STACK_TRACE_BEGINNING_MARKER.match(line)):
          in_failure_stacktrace_within_range = True
          java_stack_frame_index = 0
          continue

        if line.endswith('Summary'):
          break

        if in_failure_stacktrace_within_range:
          match = extractor_util.JAVA_STACK_TRACE_FRAME_PATTERN.search(line)

          if match:
            self.ExtractJavaFileMatch(match, signal)
            java_stack_frame_index += 1

            # Only extract the top several frames of each stack.
            if (java_stack_frame_index >=
                extractor_util.JAVA_MAXIMUM_NUMBER_STACK_FRAMES):
              in_failure_stacktrace_within_range = False

    return signal


class JunitTestExtractor(AndroidJavaTestExtractor):
  """For Junit tests."""
  TEST_START_MARKER = '[ RUN      ]'
  TEST_FAILED_MARKER = '[   FAILED ]'

  def ProcessTestFailure(self, log_lines, signal):
    in_failure_stacktrace_within_range = False
    java_stack_frame_index = 0

    # Find first failure stacktrace.
    index = 0
    end_index = len(log_lines)
    while index < end_index:  # pragma: no cover
      line = log_lines[index]
      if extractor_util.JAVA_STACK_TRACE_FRAME_PATTERN.search(line):
        in_failure_stacktrace_within_range = True
        break
      index += 1

    for line in log_lines[index:]:  # pragma: no cover
      if in_failure_stacktrace_within_range:
        match = extractor_util.JAVA_STACK_TRACE_FRAME_PATTERN.search(line)

        if match:
          self.ExtractJavaFileMatch(match, signal)
          java_stack_frame_index += 1

          # Only extract the top several frames of each stack.
          if (java_stack_frame_index >=
              extractor_util.JAVA_MAXIMUM_NUMBER_STACK_FRAMES):
            in_failure_stacktrace_within_range = False

      if self._IsStartOfStackTrace(line):
        in_failure_stacktrace_within_range = True
        java_stack_frame_index = 0
        continue

  def Extract(self, failure_log, *_):
    signal = FailureSignal()
    log_lines = failure_log.splitlines()

    index = 0
    start = index
    end = len(log_lines)

    while index < end:  # pragma: no cover
      line = log_lines[index]
      if line.startswith(self.TEST_START_MARKER):
        start = index + 1
      elif line.startswith(self.TEST_FAILED_MARKER):
        # Extract the test that failed as a possible signal.
        match = self.JAVA_TEST_NAME_PATTERN.search(line)
        self.ExtractJavaFileMatch(match, signal)

        # Extract the rest of the stacks associated with this failure.
        test_failure_lines = log_lines[start:index]
        self.ProcessTestFailure(test_failure_lines, signal)
      index += 1
    return signal


class RunhooksExtractor(Extractor):
  """For runhooks and gclient runhooks."""
  IGNORE_LINE_MARKER = re.compile('@@@.+@@@')
  STOP_MARKER = re.compile('________ running')

  def _ShouldIgnoreLine(self, line):
    return bool(self.IGNORE_LINE_MARKER.search(line))

  def Extract(self, failure_log, *_):
    signal = FailureSignal()
    log_lines = failure_log.splitlines()

    index = len(log_lines) - 1

    while index >= 0:  # pragma: no cover
      # Start at the bottom of the log and read up.
      line = log_lines[index]
      if line:
        if self.STOP_MARKER.search(line):
          break

        if not self._ShouldIgnoreLine(line):
          self.ExtractFiles(line, signal)

      index -= 1
    return signal

# TODO(lijeffrey): Several steps are named similarly and may use the same
# extractor. We may need to implement a solution to map a name to an extractor
# in a cleaner fashion, though there may be some shortcomings of special-case
# extractors that match a name pattern but do not use the same extractors.
EXTRACTORS = {
    'compile': CompileStepExtractor,
    'check_perms': CheckPermExtractor,
    'sizes': CheckSizesExtractor,
    'Instrumentation test ChromePublicTest': InstrumentationTestExtractor,
    'Instrumentation test ContentShellTest': InstrumentationTestExtractor,
    'Instrumentation test AndroidWebViewTest': InstrumentationTestExtractor,
    'Instrumentation test ChromeSyncShellTest': InstrumentationTestExtractor,
    'base_junit_tests': JunitTestExtractor,
    'chrome_junit_tests': JunitTestExtractor,
    'components_junit_tests': JunitTestExtractor,
    'content_junit_tests': JunitTestExtractor,
    'junit_unit_tests': JunitTestExtractor,
    'net_junit_tests': JunitTestExtractor,
    'runhooks': RunhooksExtractor,
    'gclient runhooks': RunhooksExtractor
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
