# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.base_handler import BaseHandler
from common.base_handler import Permission


class CheckFlake(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandleGet(self):

    # Get input parameters.
    # pylint: disable=W0612
    master_name = self.request.get('master_name').strip()
    builder_name = self.request.get('builder_name').strip()
    build_number = int(self.request.get('build_number').strip())
    test_target_name = self.request.get('test_target_name').strip()
    testcase = self.request.get('testcase').strip()

    # TODO(caiw): Get status of master_analysis from database.

    # TODO(caiw): If there is a completed master_analysis, return
    # the template which displays it.

    # TODO(caiw): If the current master_analysis has an error,
    # delete it.

    # TODO(caiw): If there is no master_analysis, create one.

    # TODO(caiw): Trigger pipeline.

    # TODO(caiw): Return the appropriate template based on the case.
