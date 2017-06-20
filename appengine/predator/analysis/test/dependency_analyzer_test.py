# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from analysis import stacktrace
from analysis.analysis_testcase import AnalysisTestCase
from analysis.dependency_analyzer import DependencyAnalyzer
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll


class DependencyAnalyzerTest(AnalysisTestCase):

  def _GetDummyDependencyAnalyzer(self):
    return DependencyAnalyzer(
        'win', '54.0.2835.0', ('54.0.2834.0', '54.0.2835.0'),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))

  @mock.patch('libs.deps.chrome_dependency_fetcher.ChromeDependencyFetcher.'
              'GetDependency')
  def testRegressionVersionDeps(self, mock_get_dependency):
    dep_data = self._GetDummyDependencyAnalyzer()
    regression_version_deps = {
        'src/': Dependency('src/', 'https://repo', 'rev')
    }
    mock_get_dependency.return_value = regression_version_deps
    self.assertEqual(dep_data.regression_version_deps,
                     regression_version_deps)

  def testRegressionVersionDepsReturnsCache(self):
    """Tests that ``regression_version_deps`` returns cached value."""
    dep_data = self._GetDummyDependencyAnalyzer()
    regression_version_deps = {
        'src/': Dependency('src/', 'https://repo', 'rev')
    }
    dep_data._regression_version_deps = regression_version_deps
    self.assertEqual(dep_data.regression_version_deps,
                     regression_version_deps)

  def testDependencies(self):
    """Tests ``GetDependencies`` gets filtered ``_regression_version_deps``."""
    dep_data = self._GetDummyDependencyAnalyzer()
    chromium_dep = Dependency('src/', 'https://repo', 'rev1')
    dep_data._regression_version_deps = {
        chromium_dep.path: chromium_dep,
        'src/dummy': Dependency('src/dummy', 'https://r', 'rev2')
    }
    stack = stacktrace.CallStack(0, frame_list=[
        stacktrace.StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacks_list = [stack]
    self.assertEqual(dep_data.GetDependencies(stacks_list),
                     {chromium_dep.path: chromium_dep})

  def testReturnEmptyDependenciesIfEmptyStacksList(self):
    """Tests that ``GetDependencies`` returns {} when stacks_list is Empty."""
    dep_data = self._GetDummyDependencyAnalyzer()
    stacks_list = []
    self.assertEqual(dep_data.GetDependencies(stacks_list), {})

  def testDependencyRollsWhenRegressionRangeIsEmpty(self):
    """Tests that ``GetDependencyRolls`` is {} if regression_range is empty."""
    dep_data = self._GetDummyDependencyAnalyzer()
    stack = stacktrace.CallStack(0, frame_list=[
        stacktrace.StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacks_list = [stack]
    dep_data._regression_range = None
    self.assertEqual(dep_data.GetDependencyRolls(stacks_list), {})

  @mock.patch('libs.deps.chrome_dependency_fetcher.ChromeDependencyFetcher.'
              'GetDependencyRollsDict')
  def testDependencyRoll(self, mock_get_dependency_rolls):
    """Tests parsing dependency rolls from regression_range."""
    dep_roll = DependencyRoll('src/', 'https://repo', 'rev1', 'rev6')
    regression_rolls = {
        dep_roll.path: dep_roll,
        'src/dummy': DependencyRoll('src/dummy', 'https://r', 'rev2', 'rev4'),
        'src/add': DependencyRoll('src/add', 'https://rr', None, 'rev5')
    }
    mock_get_dependency_rolls.return_value = regression_rolls

    dep_data = self._GetDummyDependencyAnalyzer()
    dep_data._regression_range = ('rev1', 'rev6')
    chromium_dep = Dependency('src/', 'https://repo', 'rev1')
    dep_data._regression_version_deps = {
        chromium_dep.path: chromium_dep,
        'src/dummy': Dependency('src/dummy', 'https://r', 'rev2')}
    stack = stacktrace.CallStack(0, frame_list=[
        stacktrace.StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacks_list = [stack]

    self.assertEqual(dep_data.GetDependencyRolls(stacks_list),
                     {dep_roll.path: dep_roll})
