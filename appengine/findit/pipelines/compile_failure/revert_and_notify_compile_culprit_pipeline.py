# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipelines import GeneratorPipeline
from model.base_build_model import BaseBuildModel
from pipelines.create_revert_cl_pipeline import CreateRevertCLPipeline
from pipelines.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from pipelines.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from services import constants
from services import culprit_action
from services.compile_failure import compile_culprit_action
from services.parameters import CreateRevertCLParameters
from services.parameters import CulpritActionParameters
from services.parameters import SendNotificationToIrcParameters
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SubmitRevertCLParameters
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)


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
    force_notify = culprit_action.ShouldForceNotify(culprit, pipeline_input)
    build_id = BaseBuildModel.CreateBuildId(master_name, builder_name,
                                            build_number)

    build_failure_type = failure_type.COMPILE
    revert_status = constants.SKIPPED
    commit_status = constants.SKIPPED
    if compile_culprit_action.CanAutoCreateRevert():
      revert_status = yield CreateRevertCLPipeline(
          CreateRevertCLParameters(
              cl_key=culprit,
              build_id=build_id,
              failure_type=build_failure_type))

      if compile_culprit_action.CanAutoCommitRevertByFindit():
        submit_revert_pipeline_input = self.CreateInputObjectInstance(
            SubmitRevertCLParameters,
            cl_key=culprit,
            revert_status=revert_status,
            failure_type=build_failure_type)
        commit_status = yield SubmitRevertCLPipeline(
            submit_revert_pipeline_input)

      send_notification_to_irc_input = self.CreateInputObjectInstance(
          SendNotificationToIrcParameters,
          cl_key=culprit,
          revert_status=revert_status,
          commit_status=commit_status,
          failure_type=build_failure_type)
      yield SendNotificationToIrcPipeline(send_notification_to_irc_input)

    send_notification_to_culprit_input = self.CreateInputObjectInstance(
        SendNotificationForCulpritParameters,
        cl_key=culprit,
        force_notify=force_notify,
        revert_status=revert_status,
        failure_type=build_failure_type)
    yield SendNotificationForCulpritPipeline(send_notification_to_culprit_input)
