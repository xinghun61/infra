# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import chromium_deps
from common.dependency import DependencyRoll
from crash import detect_regression_range
from crash import findit_for_fracas
from crash import fracas_parser
from crash import findit_for_crash
from crash.callstack import CallStack
from crash.component_classifier import ComponentClassifier
from crash.project_classifier import ProjectClassifier
from crash.results import MatchResult
from crash.stacktrace import Stacktrace
from crash.callstack import CallStack
from crash.test.crash_testcase import CrashTestCase


class FinditForFracasTest(CrashTestCase):

  def testFindCulpritForChromeCrashEmptyStacktrace(self):
    def _MockGetChromeDependency(*_):
      return {}

    def _MockParse(*_):
      return Stacktrace()

    self.mock(chromium_deps, 'GetChromeDependency', _MockGetChromeDependency)
    self.mock(fracas_parser.FracasParser, 'Parse', _MockParse)

    expected_results = {'found': False}
    expected_tag = {'found_suspects': False,
                    'has_regression_range': False}

    results, tag = findit_for_fracas.FindCulpritForChromeCrash(
        'signature', 'win', 'frame1\nframe2', '50.0.1234.0',
        [{'chrome_version': '50.0.1234.0', 'cpm': 0.6}])

    self.assertEqual(expected_results, results)
    self.assertEqual(expected_tag, tag)

  def testFindCulpritForChromeCrash(self):
    def _MockGetChromeDependency(*_):
      return {}

    def _MockParse(*_):
      stack = Stacktrace()
      stack.append(CallStack(0))
      return stack

    def _MockDetectRegressionRange(historic):
      if historic:
        return '50.0.1233.0', '50.0.1234.0'

      return None

    def _MockGetDEPSRollsDict(*_):
      return {'src/': DependencyRoll('src/', 'https://repo', '1', '2')}

    dummy_match_result = MatchResult(self.GetDummyChangeLog(), 'src/')
    def _MockFindItForCrash(*args):
      regression_deps_rolls = args[1]
      if regression_deps_rolls:
        return [dummy_match_result]

      return []

    def _MockComponentClassify(*_):
      return []

    def _MockProjectClassify(*_):
      return ''

    self.mock(chromium_deps, 'GetChromeDependency', _MockGetChromeDependency)
    self.mock(fracas_parser.FracasParser, 'Parse', _MockParse)
    self.mock(detect_regression_range, 'DetectRegressionRange',
              _MockDetectRegressionRange)
    self.mock(chromium_deps, 'GetDEPSRollsDict', _MockGetDEPSRollsDict)
    self.mock(findit_for_crash, 'FindItForCrash', _MockFindItForCrash)

    self.mock(ComponentClassifier, 'Classify', _MockComponentClassify)
    self.mock(ProjectClassifier, 'Classify', _MockProjectClassify)

    expected_results = {'found': False}
    expected_tag = {'found_suspects': False}

    results, tag = findit_for_fracas.FindCulpritForChromeCrash(
        'signature', 'win', 'frame1\nframe2', '50.0.1234.0',
        [{'chrome_version': '50.0.1234.0', 'cpm': 0.6}])

    expected_results = {
          'found': True,
          'suspected_project': '',
          'suspected_components': [],
          'suspected_cls': [dummy_match_result.ToDict()],
          'regression_range': ('50.0.1233.0', '50.0.1234.0'),
    }
    expected_tag = {
          'found_suspects': True,
          'has_regression_range': True,
          'solution': 'core_algorithm',
    }

    self.assertEqual(expected_results, results)
    self.assertEqual(expected_tag, tag)

    results, tag = findit_for_fracas.FindCulpritForChromeCrash(
        'signature', 'win', 'frame1\nframe2', '50.0.1234.0',
        [])

    expected_results = {
          'found': False,
          'suspected_project': '',
          'suspected_components': [],
          'suspected_cls': [],
          'regression_range': None
    }
    expected_tag = {
          'found_suspects': False,
          'has_regression_range': False,
          'solution': 'core_algorithm',
    }

    self.assertEqual(expected_results, results)
    self.assertEqual(expected_tag, tag)
