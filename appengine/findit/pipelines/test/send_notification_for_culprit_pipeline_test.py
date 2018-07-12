# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from pipelines.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from services import constants
from services import culprit_action
from services.parameters import SendNotificationForCulpritParameters
from waterfall.test import wf_testcase


class SendNotificationForCulpritPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      culprit_action, 'SendNotificationForCulprit', return_value=True)
  def testSendNotification(self, _):
    pipeline_input = SendNotificationForCulpritParameters(
        cl_key='mockurlsafekey',
        force_notify=True,
        revert_status=constants.CREATED_BY_SHERIFF,
        failure_type=failure_type.COMPILE)

    pipeline = SendNotificationForCulpritPipeline(pipeline_input)
    self.assertTrue(pipeline.run(pipeline_input))
