# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import CreateInputObjectInstance
from model.base_build_model import BaseBuildModel
from pipelines.create_revert_cl_pipeline import CreateRevertCLPipeline
from pipelines.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from pipelines.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from services import constants
from services import culprit_action
from services.test_failure import test_culprit_action
from services.parameters import CreateRevertCLParameters
from services.parameters import CulpritActionParameters
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SubmitRevertCLParameters


class RevertAndNotifyTestCulpritPipeline(GeneratorPipeline):
  """A wrapper pipeline to send notification about test failure culprits."""
  input_type = CulpritActionParameters
  output_type = bool

  def RunImpl(self, pipeline_input):

    if not culprit_action.ShouldTakeActionsOnCulprit(pipeline_input):
      return

    master_name, builder_name, build_number = (
        pipeline_input.build_key.GetParts())
    build_id = BaseBuildModel.CreateBuildId(master_name, builder_name,
                                            build_number)
    culprits = pipeline_input.culprits
    build_failure_type = failure_type.TEST

    for culprit_key in culprits.itervalues():
      revert_status = constants.SKIPPED
      if test_culprit_action.CanAutoCreateRevert(culprit_key, pipeline_input):
        revert_status = yield CreateRevertCLPipeline(
            CreateRevertCLParameters(
                cl_key=culprit_key,
                build_id=build_id,
                failure_type=build_failure_type))

        if test_culprit_action.CanAutoCommitRevertByFindit():
          submit_revert_pipeline_input = self.CreateInputObjectInstance(
              SubmitRevertCLParameters,
              cl_key=culprit_key,
              revert_status=revert_status,
              failure_type=build_failure_type)
          yield SubmitRevertCLPipeline(submit_revert_pipeline_input)

      # Checks if any of the culprits was also found by heuristic analysis,
      # if so send notification right away.
      send_notification_to_culprit_input = CreateInputObjectInstance(
          SendNotificationForCulpritParameters,
          cl_key=culprit_key,
          force_notify=culprit_action.ShouldForceNotify(culprit_key,
                                                        pipeline_input),
          revert_status=revert_status,
          failure_type=build_failure_type)
      yield SendNotificationForCulpritPipeline(
          send_notification_to_culprit_input)
