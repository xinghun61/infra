# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from gae_libs.pipeline_wrapper import BasePipeline
from services import ci_failure
from waterfall import build_util
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.submit_revert_cl_pipeline import SubmitRevertCLPipeline


class RevertAndNotifyCompileCulpritPipeline(BasePipeline):
  """A wrapper pipeline to revert culprit and send notification."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, culprits,
          heuristic_cls):
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

    force_notify = [repo_name, revision] in heuristic_cls
    build_id = build_util.CreateBuildId(master_name, builder_name, build_number)

    revert_status = yield CreateRevertCLPipeline(repo_name, revision, build_id)
    yield SubmitRevertCLPipeline(repo_name, revision, revert_status)
    yield SendNotificationToIrcPipeline(repo_name, revision, revert_status)
    yield SendNotificationForCulpritPipeline(master_name, builder_name,
                                             build_number, repo_name, revision,
                                             force_notify, revert_status)
