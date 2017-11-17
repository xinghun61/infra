# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import GeneratorPipeline
from services.compile_failure import compile_culprit_action
from services.parameters import CreateRevertCLParameters
from services.parameters import CulpritActionParameters
from services.parameters import SendNotificationToIrcParameters
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SubmitRevertCLParameters
from waterfall import build_util
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.submit_revert_cl_pipeline import SubmitRevertCLPipeline


class RevertAndNotifyCompileCulpritPipeline(GeneratorPipeline):
  """A wrapper pipeline to revert culprit and send notification."""
  input_type = CulpritActionParameters
  output_type = bool

  def RunImpl(self, pipeline_input):
    if not compile_culprit_action.ShouldTakeActionsOnCulprit(pipeline_input):
      return

    master_name, builder_name, build_number = (
        pipeline_input.build_key.GetParts())
    culprits = pipeline_input.culprits
    culprit = culprits.values()[0]
    heuristic_cls = pipeline_input.heuristic_cls
    force_notify = culprit in heuristic_cls
    build_id = build_util.CreateBuildId(master_name, builder_name, build_number)

    revert_status = yield CreateRevertCLPipeline(
        CreateRevertCLParameters(cl_key=culprit, build_id=build_id))

    submit_revert_pipeline_input = self.CreateInputObjectInstance(
        SubmitRevertCLParameters, cl_key=culprit, revert_status=revert_status)
    submitted = yield SubmitRevertCLPipeline(submit_revert_pipeline_input)

    send_notification_to_irc_input = self.CreateInputObjectInstance(
        SendNotificationToIrcParameters,
        cl_key=culprit,
        revert_status=revert_status,
        submitted=submitted)
    yield SendNotificationToIrcPipeline(send_notification_to_irc_input)

    send_notification_to_culprit_input = self.CreateInputObjectInstance(
        SendNotificationForCulpritParameters,
        cl_key=culprit,
        force_notify=force_notify,
        revert_status=revert_status)
    yield SendNotificationForCulpritPipeline(send_notification_to_culprit_input)
