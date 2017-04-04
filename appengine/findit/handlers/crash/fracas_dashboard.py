# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
from datetime import time
from datetime import timedelta
import json

from handlers.crash.dashboard import DashBoard
from libs import time_util
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class FracasDashBoard(DashBoard):

  @property
  def crash_analysis_cls(self):
    return FracasCrashAnalysis

  @property
  def client(self):
    return 'fracas'
