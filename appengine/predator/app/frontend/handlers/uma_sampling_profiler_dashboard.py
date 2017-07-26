# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.type_enums import CrashClient
from common.model.uma_sampling_profiler_analysis import (
    UMASamplingProfilerAnalysis)
from frontend.handlers.dashboard import DashBoard


class UMASamplingProfilerDashboard(DashBoard):

  @property
  def crash_analysis_cls(self):
    return UMASamplingProfilerAnalysis

  @property
  def client(self):
    return CrashClient.UMA_SAMPLING_PROFILER
