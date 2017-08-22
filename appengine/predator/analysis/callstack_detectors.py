# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import re

from analysis.type_enums import CallStackFormatType
from analysis.type_enums import LanguageType
from analysis.type_enums import SanitizerType


class StartOfCallStack(
    namedtuple('StartOfCallStack',
    ['priority', 'format_type', 'language_type', 'metadata'])):
  """Represents the start of a new callstack.

  Properties:
    priority (int): Priority of the new callstack.
    format_type (CallStackFormatType): The format of the new callstack.
    language_type (LanguageType): The language of the new callstack.
    metadata (dict): Dict of metadata for the new callstack, e.g. pid of the
      stack.
  """
  __slots__ = ()

  def __new__(cls, priority, format_type, language_type, metadata=None):
    return super(cls, StartOfCallStack).__new__(cls, priority, format_type,
                                                language_type, metadata or {})

  def __str__(self): # pragma: no cover
    return ('%s(priority = %d, format_type = %d, '
            'language_type = %d, metadata = %s)' % (self.__class__.__name__,
                                                    self.priority,
                                                    self.format_type,
                                                    self.language_type,
                                                    self.metadata))


class CallStackDetector(object):
  """Class for detecting the start of a particular sort of CallStack."""

  def __call__(self, line, flags=None):
    """Determines whether a line is the start of a new callstack or not.

    Args:
      line (str): The line to be checked.
      flags (FlagManager): manager for keeping track of parsing flags.

    Returns:
      A ``StartOfCallStack`` or None if no callstack found.
    """
    raise NotImplementedError()


class AndroidJobDetector(CallStackDetector):
  """Detects the start of an android job callstack."""
  JAVA_LANG_CALLSTACK_START_PATTERN = r'^java\.'
  JAVA_ORG_GHROMIUM_CALLSTACK_START_PATTERN = r'^org\.chromium\.'
  JAVA_CAUSED_BY_CALLSTACK_START_PATTERN = r'^Caused by:'
  JAVA_ANDROID_CALLSTACK_START_PATTERN = r'^(com\.google\.)?android\.'

  JAVA_CALLSTACK_START_REGEX = re.compile(
      '|'.join([JAVA_LANG_CALLSTACK_START_PATTERN,
                JAVA_ORG_GHROMIUM_CALLSTACK_START_PATTERN,
                JAVA_CAUSED_BY_CALLSTACK_START_PATTERN,
                JAVA_ANDROID_CALLSTACK_START_PATTERN]))

  def __call__(self, line, flags=None):
    if AndroidJobDetector.JAVA_CALLSTACK_START_REGEX.match(line):
      # Only assign the highest priority to fatal exception stack or segv
      # stack.
      if flags and flags.Get('java_main_stack_flag'):
        flags.TurnOff('java_main_stack_flag')
        return StartOfCallStack(0, CallStackFormatType.JAVA,
                                LanguageType.JAVA, {})

      return StartOfCallStack(1, CallStackFormatType.JAVA,
                              LanguageType.JAVA, {})

    return None


class SyzyasanDetector(CallStackDetector):
  """Detects the start of a syzyasn callstack."""
  SYZYASAN_CRASH_CALLSTACK_START_REGEX = re.compile(r'^Crash stack:$')
  SYZYASAN_NON_CRASH_CALLSTACK_START_REGEX = re.compile(
      r'^(Allocation|Free) stack:$')

  def __call__(self, line, flags=None):
    # In syzyasan build, new stack starts with 'crash stack:',
    # 'freed stack:', etc.
    if SyzyasanDetector.SYZYASAN_CRASH_CALLSTACK_START_REGEX.match(line):
      return StartOfCallStack(0, CallStackFormatType.SYZYASAN,
                              LanguageType.CPP, {})
    # Other callstacks all get priority 1.
    if SyzyasanDetector.SYZYASAN_NON_CRASH_CALLSTACK_START_REGEX.match(line):
      return StartOfCallStack(1, CallStackFormatType.SYZYASAN,
                              LanguageType.CPP, {})

    return None


class TsanDetector(CallStackDetector):
  """Detects the start of a thread sanitizer callstack."""
  TSAN_CRASH_CALLSTACK_START_PATTERN1 = r'^(Read|Write) of size \d+'
  TSAN_CRASH_CALLSTACK_START_PATTERN2 = r'.*(ERROR|WARNING): ?ThreadSanitizer'
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

  def __call__(self, line, flags=None):
    # Crash stack gets priority 0.
    if TsanDetector.TSAN_CRASH_CALLSTACK_START_REGEX.match(line):
      return StartOfCallStack(0, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})

    # All other stacks get priority 1.
    if TsanDetector.TSAN_NON_CRASH_CALLSTACK_START_REGEX.match(line):
      return StartOfCallStack(1, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})

    return None


class UbsanDetector(CallStackDetector):
  """Detects the start of an undefined-behavior callstack."""
  UBSAN_CALLSTACK_START_REGEX = re.compile(r'.*: runtime error: .*')

  def __call__(self, line, flags=None):
    if UbsanDetector.UBSAN_CALLSTACK_START_REGEX.match(line):
      if flags and flags.Get('is_first_stack_flag'):
        flags.TurnOff('is_first_stack_flag')
        return StartOfCallStack(0, CallStackFormatType.DEFAULT,
                                LanguageType.CPP, {})

      return StartOfCallStack(1, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})

    return None


class MsanDetector(CallStackDetector):
  """Detects the start of a memory sanitizer callstack."""
  MSAN_CALLSTACK_START_REGEX = re.compile(
      r'.*(ERROR|WARNING): ?MemorySanitizer')
  MSAN_CREATION_CALLSTACK_START_MARKER = 'Uninitialized value was created by'
  MSAN_STORAGE_CALLSTACK_START_MARKER = 'Uninitialized value was stored to'

  def __call__(self, line, flags=None):
    # Assign the only msan stack priority 0.
    if MsanDetector.MSAN_CREATION_CALLSTACK_START_MARKER in line:
      return StartOfCallStack(0, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})
    if MsanDetector.MSAN_STORAGE_CALLSTACK_START_MARKER in line:
      return StartOfCallStack(1, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})
    if MsanDetector.MSAN_CALLSTACK_START_REGEX.match(line):
      return StartOfCallStack(
          2, CallStackFormatType.DEFAULT, LanguageType.CPP, {})

    return None


class AsanDetector(CallStackDetector):
  """Detects the start of an address sanitizer callstack."""
  ASAN_CRASH_CALLSTACK_START_REGEX1 = re.compile(
      r'.*(ERROR|WARNING): ?AddressSanitizer')
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

  def __call__(self, line, flags=None):
    if AsanDetector.ASAN_CRASH_CALLSTACK_START_REGEX1.match(line):
      return StartOfCallStack(
          0, CallStackFormatType.DEFAULT, LanguageType.CPP, {})

    # Crash stack gets priority 0.
    if AsanDetector.ASAN_CRASH_CALLSTACK_START_REGEX2.match(line):
      return StartOfCallStack(0, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})

    # All other callstack gets priority 1.
    if AsanDetector.ASAN_NON_CRASH_CALLSTACK_START_PATTERN.match(line):
      return StartOfCallStack(1, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})

    return None


class LibFuzzerDetector(CallStackDetector):
  """Detects the start of a libFuzzer stack."""
  LIBFUZZER_STACK_START_REGEX = re.compile(r'.*(ERROR|WARNING): ?libFuzzer')

  def __call__(self, line, flags=None):
    if LibFuzzerDetector.LIBFUZZER_STACK_START_REGEX.match(line):
      return StartOfCallStack(
          0, CallStackFormatType.DEFAULT, LanguageType.CPP, {})


class DirectLeakDetector(CallStackDetector):
  """Detects the ``Direct-leak`` type of crash for clusterfuzz callstack."""
  DIRECT_LEAK_REGEX = re.compile(r'Direct leak of .*')

  def __call__(self, line, flags=None):
    if DirectLeakDetector.DIRECT_LEAK_REGEX.match(line):
      return StartOfCallStack(0, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})

    return None


class IndirectLeakDetector(CallStackDetector):
  """Detects the ``Indirect-leak`` type of crash for clusterfuzz callstack."""
  INDIRECT_LEAK_REGEX = re.compile(r'Indirect leak of .*')

  def __call__(self, line, flags=None):
    if IndirectLeakDetector.INDIRECT_LEAK_REGEX.match(line):
      return StartOfCallStack(0, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})

    return None


class ChromeCrashStackDetector(CallStackDetector):
  """Detects the start of an chromecrash(Fracas/Cracas) callstack."""
  CHROME_CRASH_CALLSTACK_START_REGEX = re.compile(r'CRASHED \[(.*) @ 0x(.*)\]')
  JAVA_CALLSTACK_START_REGEX = re.compile(r'\(JAVA\) CRASHED \[(.*) @ 0x(.*)\]')

  def __call__(self, line, flags=None):
    if ChromeCrashStackDetector.CHROME_CRASH_CALLSTACK_START_REGEX.match(line):
      # Fracas only provide magic signature stack (crash stack).
      return StartOfCallStack(0, CallStackFormatType.DEFAULT,
                              LanguageType.CPP, {})

    if ChromeCrashStackDetector.JAVA_CALLSTACK_START_REGEX.match(line):
      return StartOfCallStack(0, CallStackFormatType.DEFAULT,
                              LanguageType.JAVA, {})

    return None
