# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import chromium_deps
from common.dependency import DependencyRoll
from crash import detect_regression_range
from crash import findit_for_chromecrash
from crash import chromecrash_parser
from crash import findit_for_crash
from crash.component_classifier import ComponentClassifier
from crash.project_classifier import ProjectClassifier
from crash.results import MatchResult
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from crash.test.crash_testcase import CrashTestCase


class FinditForChromeCrashTest(CrashTestCase):

  def testFindCulpritForChromeCrashEmptyStacktrace(self):
    def _MockGetChromeDependency(*_):
      return {}

    def _MockParse(*_):
      return Stacktrace()

    self.mock(chromium_deps, 'GetChromeDependency', _MockGetChromeDependency)
    self.mock(chromecrash_parser.ChromeCrashParser, 'Parse', _MockParse)

    expected_results = {'found': False}
    expected_tag = {'found_suspects': False,
                    'has_regression_range': False}

    results, tag = findit_for_chromecrash.FinditForChromeCrash().FindCulprit(
        'signature', 'win', 'frame1\nframe2', '50.0.1234.0',
        [{'chrome_version': '50.0.1234.0', 'cpm': 0.6}]).ToDicts()

    self.assertEqual(expected_results, results)
    self.assertEqual(expected_tag, tag)

  def testFindCulpritForChromeCrash(self):
    def _MockGetChromeDependency(*_):
      return {}

    def _MockParse(*_):
      stack = Stacktrace()
      stack.append(CallStack(0))
      return stack

    def _MockGetDEPSRollsDict(*_):
      return {'src/': DependencyRoll('src/', 'https://repo', '1', '2'),
              'src/add': DependencyRoll('src/add', 'https://repo1', None, '2'),
              'src/delete': DependencyRoll('src/delete', 'https://repo2',
                                           '2', None)}

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
    self.mock(chromecrash_parser.ChromeCrashParser, 'Parse', _MockParse)
    self.mock(chromium_deps, 'GetDEPSRollsDict', _MockGetDEPSRollsDict)
    self.mock(findit_for_crash, 'FindItForCrash', _MockFindItForCrash)

    self.mock(ComponentClassifier, 'Classify', _MockComponentClassify)
    self.mock(ProjectClassifier, 'Classify', _MockProjectClassify)

    expected_results = {'found': False}
    expected_tag = {'found_suspects': False}

    results, tag = findit_for_chromecrash.FinditForChromeCrash().FindCulprit(
        'signature', 'win', 'frame1\nframe2', '50.0.1234.0',
        ['50.0.1233.0', '50.0.1234.0']).ToDicts()

    # TODO(wrengr): compare the Culprit object directly to these values,
    # rather than converting to dicts first. We can make a different
    # unit test for comparing the dicts, if we actually need/want to.
    expected_results = {
          'found': True,
          'suspected_project': '',
          'suspected_components': [],
          'suspected_cls': [dummy_match_result.ToDict()],
          'regression_range': ['50.0.1233.0', '50.0.1234.0']
    }
    expected_tag = {
          'found_suspects': True,
          'found_project': False,
          'found_components': False,
          'has_regression_range': True,
          'solution': 'core_algorithm',
    }

    self.assertEqual(expected_results, results)
    self.assertEqual(expected_tag, tag)

    results, tag = findit_for_chromecrash.FinditForChromeCrash().FindCulprit(
        'signature', 'win', 'frame1\nframe2', '50.0.1234.0', None).ToDicts()

    expected_results = {
          'found': False,
          'suspected_project': '',
          'suspected_components': [],
          'suspected_cls': [],
          'regression_range': None
    }
    expected_tag = {
          'found_suspects': False,
          'found_project': False,
          'found_components': False,
          'has_regression_range': False,
          'solution': 'core_algorithm',
    }

    self.assertEqual(expected_results, results)
    self.assertEqual(expected_tag, tag)
