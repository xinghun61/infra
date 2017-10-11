# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import monitoring
from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from waterfall import buildbot
from waterfall import build_util
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.submit_revert_cl_pipeline import SubmitRevertCLPipeline


def _AnyBuildSucceeded(master_name, builder_name, build_number):
  http_client = FinditHttpClient()
  latest_build_numbers = buildbot.GetRecentCompletedBuilds(
      master_name, builder_name, http_client)

  for newer_build_number in xrange(build_number + 1,
                                   latest_build_numbers[0] + 1):
    # Checks all builds after current build.
    newer_build_info = build_util.GetBuildInfo(master_name, builder_name,
                                               newer_build_number)
    if newer_build_info and newer_build_info.result in [
        buildbot.SUCCESS, buildbot.WARNINGS
    ]:
      return True

  return False


class RevertAndNotifyCulpritPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, culprits,
          heuristic_cls, try_job_type):
    assert culprits

    if _AnyBuildSucceeded(master_name, builder_name, build_number):
      # The builder has turned green, don't need to revert or send notification.
      logging.info('No revert or notification needed for culprit(s) for '
                   '%s/%s/%s since the builder has turned green.', master_name,
                   builder_name, build_number)
      return

    # There is a try job result, checks if we can revert the culprit or send
    # notification.
    if try_job_type == failure_type.COMPILE:
      # For compile, there should be only one culprit. Tries to revert it.
      culprit = culprits.values()[0]
      repo_name = culprit['repo_name']
      revision = culprit['revision']

      force_notify = [repo_name, revision] in heuristic_cls
      build_id = build_util.CreateBuildId(master_name, builder_name,
                                          build_number)

      revert_status = yield CreateRevertCLPipeline(repo_name, revision,
                                                   build_id)
      yield SubmitRevertCLPipeline(repo_name, revision, revert_status)
      yield SendNotificationToIrcPipeline(repo_name, revision, revert_status)
      yield SendNotificationForCulpritPipeline(
          master_name, builder_name, build_number, repo_name, revision,
          force_notify, revert_status)
    else:
      # Checks if any of the culprits was also found by heuristic analysis.
      monitoring.culprit_found.increment({
          'type': 'test',
          'action_taken': 'culprit_notified'
      })
      for culprit in culprits.itervalues():
        force_notify = [culprit['repo_name'],
                        culprit['revision']] in heuristic_cls
        yield SendNotificationForCulpritPipeline(
            master_name, builder_name, build_number, culprit['repo_name'],
            culprit['revision'], force_notify)
