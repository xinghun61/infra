# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import monitoring
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import CreateInputObjectInstance
from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import (
    RevertAndNotifyCulpritPipelineInput)
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationForCulpritPipelineInput)
from services import ci_failure
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)


class RevertAndNotifyTestCulpritPipeline(GeneratorPipeline):
  """A wrapper pipeline to send notification about test failure culprits."""
  input_type = RevertAndNotifyCulpritPipelineInput
  output_type = bool

  def RunImpl(self, pipeline_input):
    master_name = pipeline_input.build_key.master_name
    builder_name = pipeline_input.build_key.builder_name
    build_number = pipeline_input.build_key.build_number
    culprits = pipeline_input.culprits
    heuristic_cls = pipeline_input.heuristic_cls

    assert culprits

    # TODO(crbug/767512): Drill down to step/test level.
    if ci_failure.AnyNewBuildSucceeded(master_name, builder_name, build_number):
      # The builder has turned green, don't need to revert or send notification.
      logging.info('No revert or notification needed for culprit(s) for '
                   '%s/%s/%s since the builder has turned green.', master_name,
                   builder_name, build_number)
      return

    monitoring.culprit_found.increment({
        'type': 'test',
        'action_taken': 'culprit_notified'
    })

    # There is a try job result, checks if we can send notification.
    for culprit in culprits.itervalues():
      # Checks if any of the culprits was also found by heuristic analysis,
      # if so send notification right away.
      force_notify = culprit in heuristic_cls
      send_notification_to_culprit_input = CreateInputObjectInstance(
          SendNotificationForCulpritPipelineInput,
          cl_key=culprit,
          force_notify=force_notify,
          revert_status=None)
      yield SendNotificationForCulpritPipeline(
          send_notification_to_culprit_input)
