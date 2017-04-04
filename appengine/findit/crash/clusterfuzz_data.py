# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from collections import namedtuple

from crash import detect_regression_range
from crash.chromecrash_parser import ChromeCrashParser
from crash.clusterfuzz_parser import ClusterfuzzParser
from crash.crash_data import CrashData
from crash.stacktrace import Stacktrace
from crash.type_enums import SanitizerType
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll

_SANITIZER_SHORT_NAME_TO_SANITIZER_TYPE = {
    'SYZYASAN': SanitizerType.SYZYASAN,
    'TSAN': SanitizerType.THREAD_SANITIZER,
    'UBSAN': SanitizerType.UBSAN,
    'MSAN': SanitizerType.MEMORY_SANITIZER,
    'ASAN': SanitizerType.ADDRESS_SANITIZER
}


class ClusterfuzzData(CrashData):
  """Chrome crash report from Clusterfuzz.

  Properties:
  ...
  """

  def __init__(self, crash_data, top_n_frames=None):
    """
    Args:
      crash_data (dict): Data sent from clusterfuzz, example:
      {
          'stack_trace': '==Error==: AddressSanitizer X',  # Sample crash stack.
          # The chrome version that produced the stack trace above.
          'chrome_version': 'a6537f98f55d016e1d37dd60679253eb6e6ff8e8',
          # Whether to redo the analysis of this crash.
          'redo': True,
          # Client can provide customized data.
          'customized_data': {
              # The regression range (right now for most crashes, it is chromium
              # regression ranges).
              'regression_range': [
                  'a6537f98f55d016e1d37dd60679253eb6e6ff8e8',
                  'b63c7f98f55d016e1d37dd60679253eb6e6ff8e8'
              ],
              # All related crashed dependencies.
              'dependencies': [
                  # dependency information - [dep_path, repo_url, revision]
                  {'dep_path': 'src/',
                   'repo_url': 'https://chromium.googlesource.com/cr/src/',
                   'revision': 'a6537f9...'},
                  ...,
                  {'dep_path': 'src/v8',
                   'repo_url': 'https://chromium.googlesource.com/v8/v8/',
                   'revision': 'eqe12fe...'}
              ],
              # The regression ranges for each dependency.
              'dependency_rolls': [
                  # dependency roll information - [dep_path,
                  # repo_url, old_revision, new_revision]
                  {'dep_path': 'src/',
                   'repo_url': 'https://chromium.googlesource.com/cr/src/',
                   'old_revision': 'a6537f9...'
                   'new_revision': 'b63c7f9...'},
                  ...,
                  {'dep_path': 'src/v8',
                   'repo_url': 'https://chromium.googlesource.com/v8/v8/',
                   'old_revision': 'eqe12fe...',
                   'new_revision': 'bere3f9...'}
              ],
              'crashed_type': 'CHECK failure',
              'crashed_address': '0x000000',
              'sanitizer': 'ASAN',
              'job_type': 'android_asan_win'
              'testcase': 230193501234
          },
          'platform': 'linux',    # On which platform the crash occurs.
          # Identify which client this request is for.
          'client_id': 'clusterfuzz',
          # In clusterfuzz, the signature is the crashed_state.
          'signature': ('!data_->transaction in rankings.cc\n'
                        'anonymous namespace)::Transaction::Transaction\n'
                        'disk_cache::Rankings::Insert'),
          'crash_identifiers': {    # A list of key-value to identify a crash.
              'testcase': 230193501234
          }
      }
      top_n_frames (int): number of the frames in stacktrace we should parse.
    """
    super(ClusterfuzzData, self).__init__(crash_data)
    customized_data = crash_data['customized_data']
    self._regression_range = customized_data['regression_range']

    self._dependencies = {}
    self._dependency_rolls = {}
    self._raw_dependencies = customized_data['dependencies']
    self._raw_dependency_rolls = customized_data['dependency_rolls']

    # Delay the stacktrace parsing to the first time when stacktrace property
    # gets called.
    self._top_n_frames = top_n_frames
    self._stacktrace = None
    self._stacktrace_parsed = False

    self._crashed_type = customized_data['crashed_type']
    self._crashed_address = customized_data['crashed_address']
    self._sanitizer = _SANITIZER_SHORT_NAME_TO_SANITIZER_TYPE.get(
        customized_data['sanitizer'])
    self._job_type = customized_data['job_type']
    self._testcase = customized_data['testcase']

  @property
  def crashed_type(self):
    return self._crashed_type

  @property
  def crashed_address(self):
    return self._crashed_address

  @property
  def sanitizer(self):
    return self._sanitizer

  @property
  def job_type(self):
    return self._job_type

  @property
  def testcase(self):
    return self._testcase

  @property
  def stacktrace(self):
    """Parses stacktrace and returns parsed ``Stacktrace`` object."""
    if self._stacktrace or self._stacktrace_parsed:
      return self._stacktrace

    self._stacktrace = ClusterfuzzParser().Parse(
        self._stacktrace_str, self.dependencies, self.job_type,
        self.sanitizer, signature=self.signature,
        top_n_frames=self._top_n_frames, crashed_address=self.crashed_address)
    if not self._stacktrace:
      logging.warning('Failed to parse the stacktrace %s',
                      self._stacktrace_str)

    # Only parse stacktrace string once.
    self._stacktrace_parsed = True
    return self._stacktrace

  @property
  def regression_range(self):
    return self._regression_range

  @property
  def dependencies(self):
    if self._dependencies:
      return self._dependencies

    self._dependencies = {
        dep['dep_path']:
        Dependency(dep['dep_path'], dep['repo_url'], dep['revision'])
        for dep in self._raw_dependencies
    }
    return self._dependencies

  @property
  def dependency_rolls(self):
    if self._dependency_rolls:
      return self._dependency_rolls

    self._dependency_rolls = {
        roll['dep_path']:
        DependencyRoll(roll['dep_path'], roll['repo_url'],
                       roll['old_revision'], roll['new_revision'])
        for roll in self._raw_dependency_rolls
    }
    return self._dependency_rolls
