# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from collections import namedtuple

from analysis import detect_regression_range
from analysis.clusterfuzz_parser import ClusterfuzzParser
from analysis.crash_data import CrashData
from analysis.stacktrace import Stacktrace
from analysis.type_enums import SanitizerType
from decorators import cached_property
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
              'crash_type': 'CHECK failure',
              'crash_address': '0x000000',
              'sanitizer': 'ASAN',
              'job_type': 'android_asan_win'
              'testcase_id': 230193501234
          },
          'platform': 'linux',    # On which platform the crash occurs.
          # Identify which client this request is for.
          'client_id': 'clusterfuzz',
          # In clusterfuzz, the signature is the crash_state.
          'signature': ('!data_->transaction in rankings.cc\n'
                        'anonymous namespace)::Transaction::Transaction\n'
                        'disk_cache::Rankings::Insert'),
      }
      top_n_frames (int): number of the frames in stacktrace we should parse.
    """
    super(ClusterfuzzData, self).__init__(crash_data)
    self._crashed_version = crash_data['crash_revision']
    customized_data = crash_data['customized_data']
    self._regression_repository = customized_data['regression_range']

    self._raw_dependencies = customized_data['dependencies']
    self._raw_dependency_rolls = customized_data['dependency_rolls']

    self._top_n_frames = top_n_frames

    self._crash_type = customized_data['crash_type']
    self._crash_address = customized_data['crash_address']
    self._sanitizer = _SANITIZER_SHORT_NAME_TO_SANITIZER_TYPE.get(
        customized_data['sanitizer'])
    self._job_type = customized_data['job_type']
    self._testcase_id = str(customized_data['testcase_id'])
    self._security_flag = customized_data['security_flag']

  @property
  def crash_type(self):
    return self._crash_type

  @property
  def crash_address(self):
    return self._crash_address

  @property
  def sanitizer(self):
    return self._sanitizer

  @property
  def security_flag(self):
    return self._security_flag

  @property
  def job_type(self):
    return self._job_type

  @property
  def testcase_id(self):
    return self._testcase_id

  @property
  def regression_repository(self):
    return self._regression_repository

  @cached_property
  def stacktrace(self):
    """Parses stacktrace and returns parsed ``Stacktrace`` object."""
    stacktrace = ClusterfuzzParser().Parse(
        self._raw_stacktrace, self.dependencies, self.job_type,
        self.crash_type, signature=self.signature,
        top_n_frames=self._top_n_frames, crash_address=self.crash_address)
    if not stacktrace:
      logging.warning('Failed to parse the stacktrace %s',
                      self._raw_stacktrace)

    return stacktrace

  @cached_property
  def regression_range(self):
    if not self._regression_repository:
      return None

    return (self._regression_repository['old_revision'],
            self._regression_repository['new_revision'])

  @cached_property
  def dependencies(self):
    return {
        dep['dep_path']:
        Dependency(dep['dep_path'], dep['repo_url'], dep['revision'])
        for dep in self._raw_dependencies
    }

  @cached_property
  def dependency_rolls(self):
    return {
        roll['dep_path']:
        DependencyRoll(roll['dep_path'], roll['repo_url'],
                       roll['old_revision'], roll['new_revision'])
        for roll in self._raw_dependency_rolls
    }

  @property
  def identifiers(self):
    return self.testcase_id
