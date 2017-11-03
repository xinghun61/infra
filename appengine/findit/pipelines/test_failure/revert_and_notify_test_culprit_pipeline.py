# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import monitoring
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipelines import CreateInputObjectInstance
from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationForCulpritPipelineInput)
from services import ci_failure
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)


class RevertAndNotifyTestCulpritPipeline(BasePipeline):
  """A wrapper pipeline to send notification about test failure culprits."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, culprits,
          heuristic_cls):
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
      force_notify = [culprit['repo_name'],
                      culprit['revision']] in heuristic_cls
      send_notification_to_culprit_input = CreateInputObjectInstance(
        SendNotificationForCulpritPipelineInput,
        cl_key=CLKey(repo_name=culprit['repo_name'],
                     revision=culprit['revision']),
        force_notify=force_notify,
        revert_status=None)
      yield SendNotificationForCulpritPipeline(
          send_notification_to_culprit_input)
