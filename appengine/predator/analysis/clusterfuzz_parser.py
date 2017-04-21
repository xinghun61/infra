# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from analysis import callstack_detectors
from analysis.callstack_filters import FilterFramesAfterBlinkGeneratedCode
from analysis.callstack_filters import FilterJavaJreSdkFrames
from analysis.callstack_filters import FilterV8FramesForV8APIBindingCode
from analysis.callstack_filters import FilterV8FramesIfV8NotInTopFrames
from analysis.callstack_filters import KeepV8FramesIfV8GeneratedJITCrash
from analysis.callstack_filters import KeepTopNFrames
from analysis.flag_manager import ParsingFlag
from analysis.flag_manager import FlagManager
from analysis.stacktrace import CallStackBuffer
from analysis.stacktrace import StackFrame
from analysis.stacktrace import StacktraceBuffer
from analysis.stacktrace_parser import StacktraceParser
from analysis.type_enums import CallStackFormatType
from analysis.type_enums import LanguageType
from analysis.type_enums import SanitizerType

TOP_FRAME_HAS_NO_SYMBOLS_REGEX = re.compile(
    r'.*#0 0x[0-9a-f]+  \(<unknown module>\).*')
SUMMARY_MARKER = 'SUMMARY:'
JAVA_FATAL_EXCEPTION_REGEX = re.compile('.*FATAL EXCEPTION.*:')

ANDROID_JOB_TYPE_MARKER = 'android'
DEFAULT_TOP_N_FRAMES = 7

CALLSTACK_FLAG_GROUP = 'callstack_flags'
STACKTRACE_FLAG_GROUP = 'stacktrace_flags'

SANITIZER_TO_CALLSTACK_DETECTOR_CLASS = {
    SanitizerType.SYZYASAN: callstack_detectors.SyzyasanDetector,
    SanitizerType.THREAD_SANITIZER: callstack_detectors.TsanDetector,
    SanitizerType.UBSAN: callstack_detectors.UbsanDetector,
    SanitizerType.MEMORY_SANITIZER: callstack_detectors.MsanDetector,
    SanitizerType.ADDRESS_SANITIZER: callstack_detectors.AsanDetector
}


def GetCallStackDetector(job_type, sanitizer):
  """Returns a ``CallStackDetector`` for particular sanitizer and job type."""
  if ANDROID_JOB_TYPE_MARKER in job_type:
    return callstack_detectors.AndroidJobDetector()

  try:
    return SANITIZER_TO_CALLSTACK_DETECTOR_CLASS[sanitizer]()
  except KeyError:
    return None


class ClusterfuzzParser(StacktraceParser):

  def __init__(self):
    self.flag_manager = FlagManager()
    self.flag_manager.Register(STACKTRACE_FLAG_GROUP, ParsingFlag(
        'java_main_stack', lambda line:   # pylint: disable=W0108
            JAVA_FATAL_EXCEPTION_REGEX.match(line)))
    self.flag_manager.Register(STACKTRACE_FLAG_GROUP, ParsingFlag(
        'after_summary_line', lambda line:   # pylint: disable=W0108
            SUMMARY_MARKER in line))
    # This flag is True at the very beginning and will never be changed once it
    # is set to False.
    self.flag_manager.Register(STACKTRACE_FLAG_GROUP, ParsingFlag(
        'is_first_stack',
        lambda line: False, value=True)) # pylint: disable=W0108
    self.flag_manager.Register(CALLSTACK_FLAG_GROUP, ParsingFlag(
        'top_frame_has_no_symbol', lambda line:  # pylint: disable=W0108
            TOP_FRAME_HAS_NO_SYMBOLS_REGEX.match(line)))

  def UpdateMetadataWithFlags(self, stack_buffer):
    """Updates metadata with callstack flags. Returns updated stack buffer."""
    for flag in self.flag_manager.GetGroupFlags(CALLSTACK_FLAG_GROUP):
      stack_buffer.metadata[flag.name] = flag.value
    return stack_buffer

  def Parse(self, stacktrace_string, deps, job_type, # pylint: disable=W0221
            sanitizer, signature=None, top_n_frames=None, crash_address=None):
    """Parse clusterfuzz stacktrace string into Stacktrace instance."""
    filters = [FilterJavaJreSdkFrames(),
               KeepV8FramesIfV8GeneratedJITCrash(),
               FilterV8FramesForV8APIBindingCode(crash_address),
               FilterFramesAfterBlinkGeneratedCode(),
               FilterV8FramesIfV8NotInTopFrames(),
               KeepTopNFrames(top_n_frames or DEFAULT_TOP_N_FRAMES)]
    stacktrace_buffer = StacktraceBuffer(signature=signature, filters=filters)
    stack_detector = GetCallStackDetector(job_type, sanitizer)
    if stack_detector is None:
      logging.error('Cannot find CallStackDetector for crash %s (job type: %s)',
                    signature or '', job_type)
      return None

    # Initial background callstack which is not to be added into Stacktrace.
    stack_buffer = CallStackBuffer()
    # Reset both stacktrace and callstack flags.
    self.flag_manager.ResetAllFlags()
    for line in stacktrace_string.splitlines():
      # Note, some flags like is_first_stack may be changed inside of stack
      # detector.
      start_of_callstack = stack_detector(line, flags=self.flag_manager)

      if start_of_callstack:
        stacktrace_buffer.AddFilteredStack(
            self.UpdateMetadataWithFlags(stack_buffer))
        # Create new stack and reset callstack scope flags.
        stack_buffer = CallStackBuffer.FromStartOfCallStack(start_of_callstack)
        self.flag_manager.ResetGroupFlags(CALLSTACK_FLAG_GROUP)
      else:
        frame = StackFrame.Parse(stack_buffer.language_type,
                                 stack_buffer.format_type, line, deps,
                                 len(stack_buffer.frames))
        if frame is not None:
          stack_buffer.frames.append(frame)
        # Turn on flags if condition met.
        self.flag_manager.ConditionallyTurnOnFlags(line)

    # Add the last stack to stacktrace.
    stacktrace_buffer.AddFilteredStack(
        self.UpdateMetadataWithFlags(stack_buffer))
    return stacktrace_buffer.ToStacktrace()
