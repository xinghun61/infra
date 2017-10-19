# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipelines import CreateInputObjectInstance
from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import CreateRevertCLPipelineInput
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationToIrcPipelineInput)
from pipelines.pipeline_inputs_and_outputs import SubmitRevertCLPipelineInput
from services import ci_failure
from waterfall import build_util
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.submit_revert_cl_pipeline import SubmitRevertCLPipeline

_BYPASS_MASTER_NAME = 'chromium.sandbox'


class RevertAndNotifyCompileCulpritPipeline(BasePipeline):
  """A wrapper pipeline to revert culprit and send notification."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, culprits,
          heuristic_cls):

    if master_name == _BYPASS_MASTER_NAME:
      # This is a hack to prevent Findit taking any actions on
      # master.chromium.sandbox.
      # TODO(crbug/772972): remove the check after the master is removed.
      return

    assert culprits

    if ci_failure.AnyNewBuildSucceeded(master_name, builder_name, build_number):
      # The builder has turned green, don't need to revert or send notification.
      logging.info('No revert or notification needed for culprit(s) for '
                   '%s/%s/%s since the builder has turned green.', master_name,
                   builder_name, build_number)
      return

    # There is a try job result, checks if we can revert the culprit or send
    # notification.
    culprit = culprits.values()[0]
    repo_name = culprit['repo_name']
    revision = culprit['revision']
    cl_key = CLKey(repo_name=repo_name, revision=revision)

    force_notify = [repo_name, revision] in heuristic_cls
    build_id = build_util.CreateBuildId(master_name, builder_name, build_number)

    revert_status = yield CreateRevertCLPipeline(
        CreateRevertCLPipelineInput(
            cl_key=cl_key,
            build_id=build_id))

    submit_revert_pipeline_input = CreateInputObjectInstance(
        SubmitRevertCLPipelineInput,
        cl_key=cl_key,
        revert_status=revert_status)
    submitted = yield SubmitRevertCLPipeline(submit_revert_pipeline_input)

    send_notification_to_irc_input = CreateInputObjectInstance(
        SendNotificationToIrcPipelineInput,
        cl_key=cl_key,
        revert_status=revert_status,
        submitted=submitted)
    yield SendNotificationToIrcPipeline(send_notification_to_irc_input)

    yield SendNotificationForCulpritPipeline(master_name, builder_name,
                                             build_number, repo_name, revision,
                                             force_notify, revert_status)
