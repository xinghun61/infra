# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.type_enums import CrashClient
from common.model.crash_analysis import CrashAnalysis

# TODO(cweakliam): Rename CrashAnalysis to something more generic now that
# Predator deals with regressions as well as crashes

# TODO(cweakliam): This is currently just a skeleton. Implementation will come
# later.
class UMASamplingProfilerAnalysis(CrashAnalysis):
  """Represents an analysis of a UMA Sampling Profiler Regression."""

  def Reset(self):
    super(UMASamplingProfilerAnalysis, self).Reset()

  def Initialize(self, regression_data):
    """(Re)Initializes a CrashAnalysis ndb.Model from ``regression_data``."""
    super(UMASamplingProfilerAnalysis, self).Initialize(regression_data)

  @property
  def client_id(self):
    return CrashClient.UMA_SAMPLING_PROFILER

  @property
  def crash_url(self):
    raise NotImplementedError()

  @property
  def customized_data(self):
    raise NotImplementedError()

  def ToJson(self):
    raise NotImplementedError()
