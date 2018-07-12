# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from services import constants
from services import culprit_action
from services.parameters import SendNotificationToIrcParameters
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.test import wf_testcase


class SendNotificationToIrcPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(culprit_action, 'SendMessageToIRC', return_value=True)
  def testSendNotification(self, *_):
    revert_status = constants.CREATED_BY_FINDIT
    commit_status = constants.COMMITTED
    pipeline_input = SendNotificationToIrcParameters(
        cl_key='mockurlsafekey',
        revert_status=revert_status,
        commit_status=commit_status,
        failure_type=failure_type.COMPILE)
    pipeline = SendNotificationToIrcPipeline(pipeline_input)
    self.assertTrue(pipeline.run(pipeline_input))
