# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationForCulpritPipelineInput)
from services import gerrit
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.test import wf_testcase


class SendNotificationForCulpritPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(gerrit, 'SendNotificationForCulprit', return_value=True)
  def testSendNotification(self, _):
    repo_name = 'chromium'
    revision = 'rev1'
    pipeline_input = SendNotificationForCulpritPipelineInput(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        force_notify=True,
        revert_status=gerrit.CREATED_BY_SHERIFF)

    pipeline = SendNotificationForCulpritPipeline(pipeline_input)
    self.assertTrue(pipeline.run(pipeline_input))
