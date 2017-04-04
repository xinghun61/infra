# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll
from crash.clusterfuzz_data import ClusterfuzzData
from crash.clusterfuzz_parser import ClusterfuzzParser
from crash.crash_report import CrashReport
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.test.predator_testcase import PredatorTestCase
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from crash.type_enums import CrashClient
from crash.type_enums import SanitizerType


class CusterfuzzDataTest(StacktraceTestSuite):
  """Tests ``ClusterfuzzData`` class."""

  def testProperties(self):
    """Tests ``ClusterfuzzData`` specific properties."""
    raw_crash_data = self.GetDummyClusterfuzzData(sanitizer='ASAN')
    crash_data = ClusterfuzzData(raw_crash_data)
    self.assertEqual(crash_data.crashed_address,
                     raw_crash_data['customized_data']['crashed_address'])
    self.assertEqual(crash_data.crashed_type,
                     raw_crash_data['customized_data']['crashed_type'])
    self.assertEqual(crash_data.sanitizer,
                     SanitizerType.ADDRESS_SANITIZER)
    self.assertEqual(crash_data.job_type,
                     raw_crash_data['customized_data']['job_type'])
    self.assertEqual(crash_data.regression_range,
                     raw_crash_data['customized_data']['regression_range'])
    self.assertEqual(crash_data.testcase,
                     raw_crash_data['customized_data']['testcase'])

  def testParseStacktraceFailed(self):
    """Tests that ``stacktrace`` is None when failed to pars stacktrace."""
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData())
    self.mock(ClusterfuzzParser, 'Parse', lambda *args, **kwargs: None)
    self.assertIsNone(crash_data.stacktrace)

  def testParseStacktraceSucceeded(self):
    """Tests parsing ``stacktrace``."""
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData())
    stack = CallStack(0)
    stacktrace = Stacktrace([stack], stack)
    self.mock(ClusterfuzzParser, 'Parse',
              lambda *args, **kwargs: stacktrace)
    self._VerifyTwoStacktracesEqual(crash_data.stacktrace, stacktrace)

  def testParseStacktraceReturnsCache(self):
    """Tests that ``stacktrace`` returns cached ``_stacktrace`` value."""
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData())
    stack = CallStack(1)
    stacktrace = Stacktrace([stack], stack)
    crash_data._stacktrace = stacktrace
    self._VerifyTwoStacktracesEqual(crash_data.stacktrace, stacktrace)

  def testDependencies(self):
    """Tests ``dependencies`` property."""
    dep = Dependency('src/', 'https://repo', 'rev1')
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData(
        dependencies=[{'dep_path': dep.path,
                       'repo_url': dep.repo_url,
                       'revision': dep.revision}]))

    self.assertEqual(len(crash_data.dependencies), 1)
    self.assertTrue(dep.path in crash_data.dependencies)
    self.assertEqual(crash_data.dependencies[dep.path].path, dep.path)
    self.assertEqual(crash_data.dependencies[dep.path].repo_url, dep.repo_url)
    self.assertEqual(crash_data.dependencies[dep.path].revision, dep.revision)

  def testDependenciesReturnsCache(self):
    """Tests that ``dependencies`` returns cached ``_dependencies`` value."""
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData())
    deps = {'src/': Dependency('src/', 'https://repo', 'rev')}
    crash_data._dependencies = deps
    self.assertEqual(crash_data.dependencies, deps)

  def testDependencyRollsReturnsCache(self):
    """Tests that ``dependency_rolls`` returns cached ``_dependency_rolls``."""
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData())
    dep_roll = {'src/': DependencyRoll('src/', 'https://repo', 'rev0', 'rev3')}
    crash_data._dependency_rolls = dep_roll
    self.assertEqual(crash_data.dependency_rolls, dep_roll)

  def testDependencyRolls(self):
    """Tests ``regression_rolls`` property."""
    dep_roll = DependencyRoll('src/', 'https://repo', 'rev1', 'rev6')
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData(
        dependency_rolls=[{'dep_path': dep_roll.path,
                           'repo_url': dep_roll.repo_url,
                           'old_revision': dep_roll.old_revision,
                           'new_revision': dep_roll.new_revision}]))

    self.assertEqual(len(crash_data.dependency_rolls), 1)
    self.assertTrue(dep_roll.path in crash_data.dependency_rolls)
    self.assertEqual(crash_data.dependency_rolls[dep_roll.path].path,
                     dep_roll.path)
    self.assertEqual(crash_data.dependency_rolls[dep_roll.path].repo_url,
                     dep_roll.repo_url)
    self.assertEqual(crash_data.dependency_rolls[dep_roll.path].old_revision,
                     dep_roll.old_revision)
    self.assertEqual(crash_data.dependency_rolls[dep_roll.path].new_revision,
                     dep_roll.new_revision)
