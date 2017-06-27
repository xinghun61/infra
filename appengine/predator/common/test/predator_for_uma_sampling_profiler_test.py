# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.test.uma_sampling_profiler_data_test import TEST_DATA
from common.appengine_testcase import AppengineTestCase
from common.model.crash_config import CrashConfig
from common.predator_for_uma_sampling_profiler import (
    PredatorForUMASamplingProfiler)


class PredatorForUMASamplingProfilerTest(AppengineTestCase):
  """Tests the ``PredatorForUMASamplingProfiler`` class.

  These tests are quite basic. They are meant to just exercise this part of the
  code and check for simple errors. More thorough testing is done on the classes
  that this class uses.
  """

  def setUp(self):
    super(PredatorForUMASamplingProfilerTest, self).setUp()
    self._client = PredatorForUMASamplingProfiler(self.GetMockRepoFactory(),
                                                  CrashConfig.Get())

  def testCheckPolicy(self):
    """Tests the ``_CheckPolicy`` method."""
    regression_data = self._client.GetCrashData(TEST_DATA)
    self.assertTrue(self._client._CheckPolicy(regression_data))

  def testCreateAnalysis(self):
    """Tests that ``CreateAnalysis`` succeeds."""
    self.assertIsNotNone(self._client.CreateAnalysis({'testcase': '341335434'}))

  def testGetAnalysis(self):
    """Tests that ``GetAnalysis`` successfully retrieves the analysis."""
    crash_identifiers = {'testcase': '341335434'}
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis.put()
    self.assertEqual(self._client.GetAnalysis(crash_identifiers), analysis)

  def testPredator(self):
    """Tests that the ``_Predator`` method returns the ``_predator`` field."""
    self.assertEqual(self._client._Predator(), self._client._predator)

