# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class CallStackFormatType(object):
  JAVA = 1
  SYZYASAN = 2
  DEFAULT = 3


class CrashClient(object):
  FRACAS = 'fracas'
  CRACAS = 'cracas'
  CLUSTERFUZZ = 'clusterfuzz'
  UMA_SAMPLING_PROFILER = 'uma-sampling-profiler'


class LanguageType(object):
  CPP = 1
  JAVA = 2


class SanitizerType(object):
  ADDRESS_SANITIZER = 'ASAN'
  THREAD_SANITIZER = 'TSAN'
  MEMORY_SANITIZER = 'MSAN'
  SYZYASAN = 'SYZYASAN'
  UBSAN = 'UBSAN'
  UNSUPPORTED = 'UNSUPPORTED'


class CrashType(object):
  DIRECT_LEAK = 'Direct-leak'
  INDIRECT_LEAK = 'Indirect-leak'
  CHECK_FAILURE = 'CHECK failure'
  INTEGER_OVERFLOW = 'Integer-overflow'
  STACK_OVERFLOW = 'Stack-overflow'
  FLOATING_POINT_EXCEPTION = 'Floating-point-exception'
  NULL_DEREFERENCE = 'Null-dereference'


class LogLevel(object):
  INFO = 'info'
  WARNING = 'warning'
  ERROR = 'error'
