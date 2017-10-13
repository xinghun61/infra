# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from frontend.handlers.clusterfuzz_dashboard import ClusterfuzzDashBoard
from gae_libs.handlers.base_handler import Permission


class ClusterfuzzPublicDashBoard(ClusterfuzzDashBoard):
  PERMISSION_LEVEL = Permission.CORP_USER

  def CrashDataToDisplay(self, crash_analyses):
    """Filters security crashes and gets the crash data to display."""
    non_security_crashes = [crash for crash in crash_analyses
                            if not crash.security_flag]
    return super(ClusterfuzzPublicDashBoard, self).CrashDataToDisplay(
        non_security_crashes)
