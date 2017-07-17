# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.model.cracas_crash_analysis import CracasCrashAnalysis
from frontend.handlers.dashboard import DashBoard


class CracasDashBoard(DashBoard):

  @property
  def crash_analysis_cls(self):
    return CracasCrashAnalysis

  @property
  def client(self):
    return 'cracas'
