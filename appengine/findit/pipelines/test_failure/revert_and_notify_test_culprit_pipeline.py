# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import CreateInputObjectInstance
from services import culprit_action
from services import monitoring
from services.parameters import CulpritActionParameters
from services.parameters import SendNotificationForCulpritParameters
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)


class RevertAndNotifyTestCulpritPipeline(GeneratorPipeline):
  """A wrapper pipeline to send notification about test failure culprits."""
  input_type = CulpritActionParameters
  output_type = bool

  def RunImpl(self, pipeline_input):

    if not culprit_action.ShouldTakeActionsOnCulprit(pipeline_input):
      return

    monitoring.OnActionOnTestCulprits()

    culprits = pipeline_input.culprits
    heuristic_cls = pipeline_input.heuristic_cls
    # There is a try job result, checks if we can send notification.
    for culprit in culprits.itervalues():
      # Checks if any of the culprits was also found by heuristic analysis,
      # if so send notification right away.
      force_notify = culprit in heuristic_cls
      send_notification_to_culprit_input = CreateInputObjectInstance(
          SendNotificationForCulpritParameters,
          cl_key=culprit,
          force_notify=force_notify,
          revert_status=None)
      yield SendNotificationForCulpritPipeline(
          send_notification_to_culprit_input)
