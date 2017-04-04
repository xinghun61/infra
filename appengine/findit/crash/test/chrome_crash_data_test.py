# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from crash.chromecrash_parser import ChromeCrashParser
from crash.chrome_crash_data import ChromeCrashData
from crash.crash_report import CrashReport
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.test.predator_testcase import PredatorTestCase
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll


class ChromeCrashDataTest(StacktraceTestSuite):
  """Tests ``ChromeCrashData`` class."""

  def testProperties(self):
    """Tests ``ChromeCrashData`` specific properties."""
    raw_crash_data = self.GetDummyChromeCrashData()
    crash_data = ChromeCrashData(raw_crash_data, None)
    self.assertEqual(crash_data.channel,
                     raw_crash_data['customized_data']['channel'])
    self.assertEqual(crash_data.historical_metadata,
                     raw_crash_data['customized_data']['historical_metadata'])

  def testParseStacktraceFailed(self):
    """Tests that ``stacktrace`` is None when failed to pars stacktrace."""
    self.mock(ChromeDependencyFetcher, 'GetDependency', lambda *_: {})
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))
    self.mock(ChromeCrashParser, 'Parse', lambda *args, **kwargs: None)
    self.assertIsNone(crash_data.stacktrace)

  def testParseStacktraceSucceeded(self):
    """Tests parsing ``stacktrace``."""
    self.mock(ChromeDependencyFetcher, 'GetDependency', lambda *_: {})
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))
    stack = CallStack(0)
    stacktrace = Stacktrace([stack], stack)
    self.mock(ChromeCrashParser, 'Parse',
              lambda *args, **kwargs: stacktrace)
    self._VerifyTwoStacktracesEqual(crash_data.stacktrace, stacktrace)

  def testParseStacktraceReturnsCache(self):
    """Tests that ``stacktrace`` returns cached ``_stacktrace`` value."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    stack = CallStack(1)
    stacktrace = Stacktrace([stack], stack)
    crash_data._stacktrace = stacktrace
    self._VerifyTwoStacktracesEqual(crash_data.stacktrace, stacktrace)

  def testDetectRegressionRangeFailed(self):
    """Tests that ``regression_range`` is None when detection failed."""
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))

    with mock.patch('crash.detect_regression_range.DetectRegressionRange',
                    lambda *_: None):
      self.assertIsNone(crash_data.regression_range)

  def testDetectRegressionRangeSucceeded(self):
    """Tests detecting ``regression_range``."""
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))

    regression_range = ('1', '3')
    with mock.patch('crash.detect_regression_range.DetectRegressionRange',
                    lambda *_: regression_range):
      self.assertEqual(crash_data.regression_range, regression_range)

  def testDetectRegressionRangeReturnsCache(self):
    """Tests that ``regression_range`` returns cached ``_regression_range``."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    regression_range = ('1', '5')
    crash_data._regression_range = regression_range
    self.assertEqual(crash_data.regression_range, regression_range)

  def testCrashedVersionDepsReturnsCache(self):
    """Tests that ``_CrashedVersionDeps`` returns cached value."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    crashed_version_deps = {'src/': Dependency('src/', 'https://repo', 'rev')}
    crash_data._crashed_version_deps = crashed_version_deps
    self.assertEqual(crash_data._CrashedVersionDeps(), crashed_version_deps)

  def testDependencies(self):
    """Tests that ``dependencies`` returns filtered ``_CrashedVersionDeps``."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    chromium_dep = Dependency('src/', 'https://repo', 'rev1')
    crash_data._crashed_version_deps = {
        chromium_dep.path: chromium_dep,
        'src/dummy': Dependency('src/dummy', 'https://r', 'rev2')}
    stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacktrace = Stacktrace([stack], stack)
    crash_data._stacktrace = stacktrace
    self.assertEqual(crash_data.dependencies,
                     {chromium_dep.path: chromium_dep})

  def testReturnEmptyDependenciesIfEmptyStacktrace(self):
    """Tests that ``dependencies`` returns {} when stacktrace is None."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    self.assertEqual(crash_data.dependencies, {})

  def testDependenciesReturnsCache(self):
    """Tests that ``dependencies`` returns cached ``_dependencies`` value."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    crashed_version_deps = {'src/': Dependency('src/', 'https://repo', 'rev')}
    crash_data._dependencies = crashed_version_deps
    self.assertEqual(crash_data.dependencies, crashed_version_deps)

  def testDependencyRollsReturnsCache(self):
    """Tests that ``dependency_rolls`` returns cached ``_dependency_rolls``."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    dep_roll = {'src/': DependencyRoll('src/', 'https://repo', 'rev0', 'rev3')}
    crash_data._dependency_rolls = dep_roll
    self.assertEqual(crash_data.dependency_rolls, dep_roll)

  def testDependencyRollsWhenRegressionRangeIsEmpty(self):
    """Tests that ``regression_rolls`` is {} when regression_range is empty."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    crash_data._regression_range = None
    self.assertEqual(crash_data.dependency_rolls, {})

  def testDependencyRoll(self):
    """Tests parsing ``regression_rolls`` from regression_range."""
    dep_roll = DependencyRoll('src/', 'https://repo', 'rev1', 'rev6')
    regression_rolls = {
        dep_roll.path: dep_roll,
        'src/dummy': DependencyRoll('src/dummy', 'https://r', 'rev2', 'rev4'),
        'src/add': DependencyRoll('src/add', 'https://rr', None, 'rev5')
    }

    self.mock(ChromeDependencyFetcher, 'GetDependencyRollsDict',
              lambda *_: regression_rolls)
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))

    crash_data._regression_range = ('rev1', 'rev6')
    chromium_dep = Dependency('src/', 'https://repo', 'rev1')
    crash_data._crashed_version_deps = {
        chromium_dep.path: chromium_dep,
        'src/dummy': Dependency('src/dummy', 'https://r', 'rev2')}
    stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacktrace = Stacktrace([stack], stack)
    crash_data._stacktrace = stacktrace

    self.assertEqual(crash_data.dependency_rolls, {dep_roll.path: dep_roll})
