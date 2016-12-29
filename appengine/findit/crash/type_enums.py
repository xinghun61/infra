# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import OrderedDict


class CallStackFormatType(object):
  JAVA = 1
  SYZYASAN = 2
  DEFAULT = 3


class CrashClient(object):
  FRACAS = 'fracas'
  CRACAS = 'cracas'
  CLUSTERFUZZ = 'clusterfuzz'


class LanguageType(object):
  CPP = 1
  JAVA = 2


class SanitizerType(object):
  ADDRESS_SANITIZER = 1,
  THREAD_SANITIZER = 2,
  MEMORY_SANITIZER = 3,
  SYZYASAN = 4,
  UBSAN = 5
  UNSUPPORTED = 6

  stacktrace_marker_to_sanitizer = {
      'AddressSanitizer': ADDRESS_SANITIZER,
      'ThreadSanitizer': THREAD_SANITIZER,
      'MemorySanitizer': MEMORY_SANITIZER,
      'syzyasan': SYZYASAN,
      ': runtime error:': UBSAN
  }

  # Some signature may contain others, for example 'syzyasan' contains 'asan',
  # in order to match signature in build type correctly, use ordered dict with
  # decreasing length of signature.
  job_type_marker_to_sanitizer = OrderedDict(
      [('syzyasan', SYZYASAN),
       ('ubsan', UBSAN),
       ('asan', ADDRESS_SANITIZER),
       ('msan', MEMORY_SANITIZER),
       ('tsan', THREAD_SANITIZER)])

  @staticmethod
  def GetSanitizerType(job_type, stacktrace_string):
    for marker, sanitizer_type in (
        SanitizerType.job_type_marker_to_sanitizer.iteritems()):
      if marker.lower() in job_type.lower():
        return sanitizer_type

    for marker, sanitizer_type in (
        SanitizerType.stacktrace_marker_to_sanitizer.iteritems()):
      if marker.lower() in stacktrace_string.lower():
        return sanitizer_type

    return SanitizerType.UNSUPPORTED
