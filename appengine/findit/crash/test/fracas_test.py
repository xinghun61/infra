# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import chromium_deps
from crash import detect_regression_range
from crash import fracas
from crash import fracas_parser
from crash import findit_for_crash
from crash.stacktrace import Stacktrace
from crash.test.crash_testcase import CrashTestCase


class FracasTest(CrashTestCase):

  def testFindCulpritForChromeCrash(self):
    def _MockGetChromeDependency(*_):
      return {}

    def _MockParse(*_):
      return Stacktrace()

    def _MockDetectRegressionRange(historic):
      if historic:
        return '50.0.1233.0', '50.0.1234.0'

      return None

    def _MockGetDEPSRollsDict(*_):
      return {}

    def _MockFindItForCrash(*_):
      return []

    self.mock(chromium_deps, 'GetChromeDependency', _MockGetChromeDependency)
    self.mock(fracas_parser.FracasParser, 'Parse', _MockParse)
    self.mock(detect_regression_range, 'DetectRegressionRange',
              _MockDetectRegressionRange)
    self.mock(chromium_deps, 'GetDEPSRollsDict', _MockGetDEPSRollsDict)
    self.mock(findit_for_crash, 'FindItForCrash', _MockFindItForCrash)

    expected_results = {
        'found': False,
        'suspected_project': '',
        'suspected_components': [],
        'culprits': [],
    }

    expected_tag = {
        'found_suspects': False,
        'has_regression_range': True,
        'solution': 'core_algorithm',
    }

    results, tag = fracas.FindCulpritForChromeCrash(
        'signature', 'win', 'frame1\nframe2', '50.0.1234.0',
        [{'chrome_version': '50.0.1234.0', 'cpm': 0.6}])

    self.assertEqual(expected_results, results)
    self.assertEqual(expected_tag, tag)

    results, tag = fracas.FindCulpritForChromeCrash(
        'signature', 'win', 'frame1\nframe2', '50.0.1234.0', [])

    expected_tag['has_regression_range'] = False
    self.assertEqual(expected_tag, tag)
