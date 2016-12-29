# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType
from crash.type_enums import SanitizerType


class CallStackDetector(object):
  """Class for detecting the start of a particular sort of CallStack."""

  # TODO(crbug.com/677321) Make the return to be a namedtuple.
  def IsStartOfNewCallStack(self, line, flags=None):
    """Determines whether a line is the start of a new callstack or not.

    Args:
      line (str): The line to be checked.
      flags (FlagManager): manager for keeping track of parsing flags.

    Returns:
      A tuple -
      (is_new_callstack, priority, format_type, language_type, metadata)
      is_new_callstack (bool): Boolean indicating whether this is the start of
        a new callstack.
      priority (int): Priority of a callstack.
      format_type (CallStackFormatType): The format of the new callstack, or
        None if there is no new callstack.
      language_type (LanguageType): The language of the new callstack, or None
        if there is no new callstack.
      metadata (dict): Dict of metadata for the new callstack, e.g. pid of
        the stack.
    """
    raise NotImplementedError()


class AndroidJobDetector(CallStackDetector):
  """Detects the start of an android job callstack."""
  JAVA_LANG_CALLSTACK_START_PATTERN = r'^java\.[A-Za-z0-9$._]+'
  JAVA_ORG_GHROMIUM_CALLSTACK_START_PATTERN = r'^org\.chromium\.[A-Za-z0-9$._]+'
  JAVA_CAUSED_BY_CALLSTACK_START_PATTERN = r'^Caused by:'
  JAVA_ANDROID_CALLSTACK_START_PATTERN = (
      r'^(com\.google\.)?android\.[A-Za-z0-9$._]+')

  JAVA_CALLSTACK_START_REGEX = re.compile(
      '|'.join([JAVA_LANG_CALLSTACK_START_PATTERN,
                JAVA_ORG_GHROMIUM_CALLSTACK_START_PATTERN,
                JAVA_CAUSED_BY_CALLSTACK_START_PATTERN,
                JAVA_ANDROID_CALLSTACK_START_PATTERN]))

  def IsStartOfNewCallStack(self, line, flags=None):
    if AndroidJobDetector.JAVA_CALLSTACK_START_REGEX.match(line):
      # Only assign the highest priority to fatal exception stack or segv
      # stack.
      if flags and flags.Get('java_main_stack_flag'):
        flags.TurnOff('java_main_stack_flag')
        return True, 0, CallStackFormatType.JAVA, LanguageType.JAVA, {}

      return True, 1, CallStackFormatType.JAVA, LanguageType.JAVA, {}

    return False, None, None, None, None


class SyzyasanDetector(CallStackDetector):
  """Detects the start of a syzyasn callstack."""
  SYZYASAN_CRASH_CALLSTACK_START_REGEX = re.compile(r'^Crash stack:$')
  SYZYASAN_NON_CRASH_CALLSTACK_START_REGEX = re.compile(r'^(?!Crash).* stack:$')

  def IsStartOfNewCallStack(self, line, flags=None):
    # In syzyasan build, new stack starts with 'crash stack:',
    # 'freed stack:', etc.
    if SyzyasanDetector.SYZYASAN_CRASH_CALLSTACK_START_REGEX.match(line):
      return True, 0, CallStackFormatType.SYZYASAN, LanguageType.CPP, {}
    # Other callstacks all get priority 1.
    if SyzyasanDetector.SYZYASAN_NON_CRASH_CALLSTACK_START_REGEX.match(line):
      return True, 1, CallStackFormatType.SYZYASAN, LanguageType.CPP, {}

    return False, None, None, None, None


class TsanDetector(CallStackDetector):
  """Detects the start of a thread sanitizer callstack."""
  TSAN_CRASH_CALLSTACK_START_PATTERN1 = r'^(Read|Write) of size \d+'
  TSAN_CRASH_CALLSTACK_START_PATTERN2 = r'^[A-Z]+: ThreadSanitizer'
  TSAN_ALLOCATION_CALLSTACK_START_PATTERN = (
      r'^Previous (write|read) of size \d+')
  TSAN_LOCATION_CALLSTACK_START_PATTERN = (
      r'^Location is heap block of size \d+')

  TSAN_CRASH_CALLSTACK_START_REGEX = re.compile(
      '|'.join([TSAN_CRASH_CALLSTACK_START_PATTERN1,
                TSAN_CRASH_CALLSTACK_START_PATTERN2]))

  TSAN_NON_CRASH_CALLSTACK_START_REGEX = re.compile(
      '|'.join([TSAN_ALLOCATION_CALLSTACK_START_PATTERN,
                TSAN_LOCATION_CALLSTACK_START_PATTERN]))

  def IsStartOfNewCallStack(self, line, flags=None):
    # Crash stack gets priority 0.
    if TsanDetector.TSAN_CRASH_CALLSTACK_START_REGEX.match(line):
      return True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}

    # All other stacks get priority 1.
    if TsanDetector.TSAN_NON_CRASH_CALLSTACK_START_REGEX.match(line):
      return True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}

    return False, None, None, None, None


class UbsanDetector(CallStackDetector):
  """Detects the start of an undefined-behavior callstack."""
  UBSAN_CALLSTACK_START_REGEX = re.compile(r'^.*: runtime error: .*$')

  def IsStartOfNewCallStack(self, line, flags=None):
    if UbsanDetector.UBSAN_CALLSTACK_START_REGEX.match(line):
      if flags and flags.Get('is_first_stack_flag'):
        flags.TurnOff('is_first_stack_flag')
        return True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}

      return True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}

    return False, None, None, None, None


class MsanDetector(CallStackDetector):
  """Detects the start of a memory sanitizer callstack."""
  MSAN_CALLSTACK_START_REGEX = re.compile(r'^==(\d+)== ?([A-Z]+:|\w+Sanitizer)')
  MSAN_CREATION_CALLSTACK_START_MARKER = 'Uninitialized value was created by'
  MSAN_STORAGE_CALLSTACK_START_MARKER = 'Uninitialized value was stored to'

  def IsStartOfNewCallStack(self, line, flags=None):
    # Assign the only msan stack priority 0.
    if MsanDetector.MSAN_CREATION_CALLSTACK_START_MARKER in line:
      return True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}
    if MsanDetector.MSAN_STORAGE_CALLSTACK_START_MARKER in line:
      return True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}
    msan_callstack_start_regex = (
        MsanDetector.MSAN_CALLSTACK_START_REGEX.match(line))
    if msan_callstack_start_regex:
      return (True, 2, CallStackFormatType.DEFAULT, LanguageType.CPP,
              {'pid': int(msan_callstack_start_regex.group(1).strip())})

    return False, None, None, None, None


class AsanDetector(CallStackDetector):
  """Detects the start of an address sanitizer callstack."""
  ASAN_CRASH_CALLSTACK_START_REGEX1 = re.compile(
      r'^==(\d+)== ?([A-Z]+:|\w+Sanitizer)')
  ASAN_CRASH_CALLSTACK_START_REGEX2 = re.compile(
      r'^(READ|WRITE) of size \d+ at|^backtrace:')

  ASAN_FREED_CALLSTACK_START_PATTERN = (
      r'^freed by thread T\d+ (.* )?here:')
  ASAN_ALLOCATION_CALLSTACK_START_PATTERN = (
      r'^(previously )?allocated by thread T\d+ (.* )?here:')
  ASAN_OTHER_CALLSTACK_START_PATTERN = (
      r'^Thread T\d+ (.* )?created by')

  ASAN_NON_CRASH_CALLSTACK_START_PATTERN = re.compile(
      '|'.join([ASAN_FREED_CALLSTACK_START_PATTERN,
                ASAN_ALLOCATION_CALLSTACK_START_PATTERN,
                ASAN_OTHER_CALLSTACK_START_PATTERN]))

  def IsStartOfNewCallStack(self, line, flags=None):
    asan_crash_callstack_start_regex1_match = (
        AsanDetector.ASAN_CRASH_CALLSTACK_START_REGEX1.match(line))
    if asan_crash_callstack_start_regex1_match:
      return (True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP,
              {'pid': int(
                  asan_crash_callstack_start_regex1_match.group(1).strip())})

    # Crash stack gets priority 0.
    if AsanDetector.ASAN_CRASH_CALLSTACK_START_REGEX2.match(line):
      return True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}

    # All other callstack gets priority 1.
    if AsanDetector.ASAN_NON_CRASH_CALLSTACK_START_PATTERN.match(line):
      return True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}

    return False, None, None, None, None


class ChromeCrashStackDetector(CallStackDetector):
  """Detects the start of an chromecrash(Fracas/Cracas) callstack."""
  CHROME_CRASH_CALLSTACK_START_REGEX = re.compile(r'CRASHED \[(.*) @ 0x(.*)\]')
  JAVA_CALLSTACK_START_REGEX = re.compile(r'\(JAVA\) CRASHED \[(.*) @ 0x(.*)\]')

  def IsStartOfNewCallStack(self, line, flags=None):
    if ChromeCrashStackDetector.CHROME_CRASH_CALLSTACK_START_REGEX.match(line):
      # Fracas only provide magic signature stack (crash stack).
      return True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}

    if ChromeCrashStackDetector.JAVA_CALLSTACK_START_REGEX.match(line):
      return True, 0, CallStackFormatType.DEFAULT, LanguageType.JAVA, {}

    return False, None, None, None, None
