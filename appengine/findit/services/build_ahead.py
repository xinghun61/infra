# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for build-ahead related operations.

It provides functions for:
  * Triggering a build-ahead on a specific builder.
"""
import json
import logging

from common.findit_http_client import FinditHttpClient
from common.waterfall import buildbucket_client
from services import swarmbot_util
from waterfall import waterfall_config


def TriggerBuildAhead(wf_master, wf_builder, bot):
  """Starts a ToT compile tryjob on `bot`, in the appropriate cache.

  This function creates a request for a tryjob as similar as possible to what a
  compile failure analysis would be, except it does it at the most recent
  revision, and without specifying a target or a callback.

  Args:
    wf_master: The main waterfall master.
    wf_builder: The main waterfall builder whose configuration we want to match.
    bot: The 'id' dimension of the particular swarming bot that should run this.
  Returns:
    (buildbucket_client.BuildbucketError, buildbucket_client.BuildbucketBuild)
    The second element of the tuple can be used to get the buildbucket id, and
    later query the status of the job by calling buildbucket_client.GetTryjobs.
  """
  cache_name = swarmbot_util.GetCacheName(wf_master, wf_builder)
  recipe = 'findit/chromium/compile'
  dimensions = waterfall_config.GetTrybotDimensions(wf_master, wf_builder)
  dimensions = waterfall_config._MergeDimensions(dimensions, ['id:%s' % bot])
  master_name, builder_name = waterfall_config.GetSwarmbucketBot(
      wf_master, wf_builder)
  # By setting the revisions to (HEAD~1, HEAD), we get the findit compile recipe
  # to do a build at the tip of the tree without adding any special cases to the
  # recipe.
  good_revision = 'HEAD~1'
  bad_revision = 'HEAD'

  build_ahead_tryjob = buildbucket_client.TryJob(
      master_name=master_name,
      builder_name=builder_name,
      properties={
          'recipe':
              recipe,
          'bad_revision':
              bad_revision,
          'good_revision':
              good_revision,
          'target_mastername':
              wf_master,
          'target_buildername':
              wf_builder,
          # TODO(robertocn): Remove this hack. This prop is still required for
          # chromium_tests recipe module to configure the recipe correctly.
          'mastername':
              waterfall_config.GetWaterfallTrybot(
                  wf_master, wf_builder, force_buildbot=True)[0],
          'suspected_revisions': [],
      },
      tags=[],
      additional_build_parameters=None,
      cache_name=cache_name,
      dimensions=dimensions)
  return buildbucket_client.TriggerTryJobs([build_ahead_tryjob])[0]


def TreeIsOpen():
  """Determine whether the chromium tree is currently open."""
  url = 'https://chromium-status.appspot.com/allstatus'
  params = {
      'limit': '1',
      'fomrat': 'json',
  }
  client = FinditHttpClient()
  status_code, content = client.Get(url, params)

  if status_code == 200:
    try:
      states = json.loads(str(content))
      if states and states[0].get('general_state') == 'open':
        return True
    except ValueError, ve:
      logging.exception('Could not parse chromium tree status: %s', ve)
  return False
