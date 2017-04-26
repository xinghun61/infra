# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_report import CrashReport
from analysis.crash_report import _FrozenDict
from analysis.stacktrace import CallStack
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from analysis.type_enums import CallStackFormatType
from analysis.type_enums import LanguageType
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.gitiles_repository import GitilesRepository

DUMMY_CALLSTACKS = [
    CallStack(0, [], CallStackFormatType.DEFAULT, LanguageType.CPP),
    CallStack(1, [], CallStackFormatType.DEFAULT, LanguageType.CPP)]
DUMMY_REPORT = CrashReport(
    None, None, None, Stacktrace(DUMMY_CALLSTACKS, DUMMY_CALLSTACKS[0]),
    (None, None), None, None)


class FrozenDictTest(AnalysisTestCase):
  def testHash(self):
    """Test that ``_FrozenDict`` does not throw an exception in ``hash``."""
    try:
        _h = hash(_FrozenDict({'a': 1, 'b': 2, 'c': 3}))
    except TypeError as e: # pragma: no cover
      if 'unhashable type' in str(e):
        self.fail('_FrozenDict.__hash__ does not work')
      else:
        raise e


class CrashReportTest(AnalysisTestCase):

  def testDependenciesAndDependencyRollsIsFrozenDict(self):
    crash_report = CrashReport(
        'rev', 'sig', 'win', None, ('1', '3'),
        {'src/': Dependency('src/', 'http://repo', '5')},
        {'src/': DependencyRoll('src/', 'http://repo', '1', '3')})
    self.assertTrue(isinstance(crash_report.regression_range, tuple))
    self.assertTrue(isinstance(crash_report.dependencies, _FrozenDict))
    self.assertTrue(isinstance(crash_report.dependency_rolls, _FrozenDict))
