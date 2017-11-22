# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.analysis_testcase import AnalysisTestCase
from analysis.culprit import Culprit


class CulpritTest(AnalysisTestCase):

  def testFieldsProperty(self):
    culprit = Culprit('', ['Blink>DOM'], [], None, 'core_algorithm')
    self.assertEqual(culprit.fields, ('project', 'components', 'suspected_cls',
                                      'regression_range', 'algorithm'))
  def testToDictsDroppingEmptyFields(self):
    culprit = Culprit('', [], [], [], 'core_algorithm')
    self.assertTupleEqual(culprit.ToDicts(),
                          ({'found': False},
                           {'found_suspects': False,
                            'found_project': False,
                            'found_components': False,
                            'has_regression_range': False,
                            'solution': 'core_algorithm'}))

  def testToDicts(self):
    cl = self.GetDummyChangeLog()
    culprit = Culprit('proj', ['comp'], [cl], ['50.0.1234.1', '50.0.1234.2'],
                      'core_algorithm')
    self.assertTupleEqual(culprit.ToDicts(),
                          ({'found': True,
                            'regression_range': ['50.0.1234.1', '50.0.1234.2'],
                            'suspected_project': 'proj',
                            'suspected_components': ['comp'],
                            'suspected_cls': [cl.ToDict()]},
                           {'found_suspects': True,
                            'found_project': True,
                            'found_components': True,
                            'has_regression_range': True,
                            'solution': 'core_algorithm'}))
