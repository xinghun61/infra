# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.type_enums import CrashClient
from common.model.uma_sampling_profiler_analysis import (
    UMASamplingProfilerAnalysis)
from frontend.handlers.uma_sampling_profiler_dashboard import (
    UMASamplingProfilerDashboard)
from testing_utils import testing


class UMASamplingProfilerDashBoardTest(testing.AppengineTestCase):

  def testCrashAnalysisCls(self):
    """Tests that the crash_analysis_cls is UMASamplingProfilerAnalysis."""
    dashboard = UMASamplingProfilerDashboard()
    self.assertEqual(dashboard.crash_analysis_cls, UMASamplingProfilerAnalysis)

  def testClient(self):
    """Tests that the client is CrashClient.UMA_SAMPLING_PROFILER."""
    dashboard = UMASamplingProfilerDashboard()
    self.assertEqual(dashboard.client, CrashClient.UMA_SAMPLING_PROFILER)

