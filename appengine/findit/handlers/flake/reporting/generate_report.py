# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from services.flake_reporting import component


class PrepareFlakinessReport(BaseHandler):
  """Create a report of flakiness by component and test"""

  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    component.Report()
