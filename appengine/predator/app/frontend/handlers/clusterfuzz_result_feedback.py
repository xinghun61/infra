# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.type_enums import CrashClient
from frontend.handlers.result_feedback import ResultFeedback
from gae_libs.handlers.base_handler import Permission


class ClusterfuzzResultFeedback(ResultFeedback):
  PERMISSION_LEVEL = Permission.ADMIN

  @property
  def client(self):
    return CrashClient.CLUSTERFUZZ
