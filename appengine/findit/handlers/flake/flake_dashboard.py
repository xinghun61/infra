# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.base_handler import BaseHandler
from common.base_handler import Permission
from model.flake.master_flake_analysis import MasterFlakeAnalysis


class FlakeDashboard(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandleGet(self):
    master_flake_analyses = MasterFlakeAnalysis.query().order(
        -MasterFlakeAnalysis.updated_time).fetch()
    data = {
        'master_flake_analyses': master_flake_analyses
    }
    return {
        'template': 'flake/dashboard.html',
        'data': data
    }
