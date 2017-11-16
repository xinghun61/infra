# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from gae_libs.pipelines import GeneratorPipeline
from services import ci_failure
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

_BYPASS_MASTER_NAME = 'chromium.sandbox'


class RevertAndNotifyCompileCulpritPipeline(GeneratorPipeline):
  """A wrapper pipeline to revert culprit and send notification."""
  input_type = CulpritActionParameters
  output_type = bool

  def RunImpl(self, pipeline_input):
    master_name = pipeline_input.build_key.master_name
    builder_name = pipeline_input.build_key.builder_name
    build_number = pipeline_input.build_key.build_number
    culprits = pipeline_input.culprits
    heuristic_cls = pipeline_input.heuristic_cls

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
