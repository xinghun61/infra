# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from collections import namedtuple

from analysis.chromecrash_parser import ChromeCrashParser
from analysis.stacktrace import Stacktrace

PLATFORM_TO_NORMALIZED_PLATFORM = {'linux': 'unix'}


class CrashData(object):
  """An abstract class representing crash data sent by clients.

  This class is constructed from the raw data that clients sent to Predator, and
  do all necessary analysis to get all information that Predator library needs,
  which means all information for us to create ``CrashReport`` for Predator to
  analyze.

  Properties:
    identifiers (dict): The key value pairs to uniquely identify a
      ``CrashData``.
    crashed_version (str): The version of project in which the crash occurred.
    signature (str): The signature of the crash.
    platform (str): The platform name; e.g., 'win', 'mac', 'linux', 'android',
      'ios', etc.
    stacktrace (Stacktrace): Needs to be implemented.
    regression_range (pair or None): Needs to be implemented.
    dependencies (dict): Needs to be implemented.
    dependency_rolls (dict) Needs to be implemented.

  """
  def __init__(self, crash_data):
    """
    Args:
      crash_data (dict): Dicts sent through Pub/Sub by clients. Example:
      {
          'stack_trace': 'CRASHED [0x43507378...',
          # The Chrome version that produced the stack trace above.
          'chrome_version': '52.0.2743.41',
          # Client could provide customized data.
          'customized_data': {  # client-specific data
              ...
          },
          'platform': 'mac',    # On which platform the crash occurs.
          'client_id': 'fracas',   # Identify which client this request is from.
          'signature': '[ThreadWatcher UI hang] base::RunLoopBase::Run',
          'crash_identifiers': {    # A list of key-value to identify a crash.
            ...
          }
      }
    """
    self._crashed_version = crash_data['chrome_version']
    self._signature = crash_data['signature']
    self._platform = self.NormalizePlatform(crash_data['platform'])
    # The raw_stacktrace can be a string or a list of strings, or any json
    # format data.
    self._raw_stacktrace = crash_data['stack_trace'] or ''

  @property
  def raw_stacktrace(self):
    return self._raw_stacktrace

  @property
  def crashed_version(self):
    return self._crashed_version

  @property
  def signature(self):
    return self._signature

  @property
  def platform(self):
    return self._platform

  @platform.setter
  def platform(self, platform):
    self._platform = self.NormalizePlatform(platform)

  @property
  def stacktrace(self):
    raise NotImplementedError()

  @property
  def regression_range(self):
    raise NotImplementedError()

  @property
  def dependencies(self):
    raise NotImplementedError()

  @property
  def dependency_rolls(self):
    raise NotImplementedError()

  @property
  def identifiers(self):
    raise NotImplementedError()

  def NormalizePlatform(self, platform):
    """Normalizes platform name."""
    return PLATFORM_TO_NORMALIZED_PLATFORM.get(platform, platform)
