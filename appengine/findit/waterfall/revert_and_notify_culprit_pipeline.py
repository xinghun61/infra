# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)


class RevertAndNotifyCulpritPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, culprits, heuristic_cls,
      compile_suspected_cl, try_job_type):
    if culprits:
      # There is a try job result, checks if we can revert the culprit or send
      # notification.
      if try_job_type == failure_type.COMPILE:
        # For compile, there should be only one culprit. Tries to revert it.
        culprit = culprits.values()[0]
        repo_name = culprit['repo_name']
        revision = culprit['revision']

        send_notification_right_now = [repo_name, revision] in heuristic_cls

        revert_status = yield CreateRevertCLPipeline(
            master_name, builder_name, build_number, repo_name, revision)
        yield SendNotificationForCulpritPipeline(
            master_name, builder_name, build_number, culprit['repo_name'],
            culprit['revision'], send_notification_right_now, revert_status)
      else:
        # Checks if any of the culprits was also found by heuristic analysis.
        for culprit in culprits.itervalues():
          send_notification_right_now = [
              culprit['repo_name'], culprit['revision']] in heuristic_cls
          yield SendNotificationForCulpritPipeline(
              master_name, builder_name, build_number, culprit['repo_name'],
              culprit['revision'], send_notification_right_now)
    elif compile_suspected_cl:  # pragma: no branch
      # A special case where try job didn't find any suspected cls, but
      # heuristic found a suspected_cl.
      yield SendNotificationForCulpritPipeline(
          master_name, builder_name, build_number,
          compile_suspected_cl['repo_name'], compile_suspected_cl['revision'],
          True)
