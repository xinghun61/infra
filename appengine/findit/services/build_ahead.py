# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for build-ahead related operations.

It provides functions for:
  * Triggering a build-ahead on a specific builder.
"""
import json
import logging
import random

from common.findit_http_client import FinditHttpClient
from common.waterfall import buildbucket_client
from model.build_ahead_try_job import BuildAheadTryJob
from services import git
from services import swarmbot_util
from waterfall import waterfall_config

LOW_COMMITS_PER_HOUR = 3
PLATFORM_DIMENSION_MAP = {
    'mac': ['os:Mac'],
    'win': ['os:Windows'],
    'unix': ['os:Linux'],
    'android': ['os:Linux'],
}
BUILD_AHEAD_PLATFORMS = sorted(PLATFORM_DIMENSION_MAP.keys())


def _LowRepoActivity():
  """Returns true if 3 or fewer commits have landed in the last hour.

  The reasoning is: a typical builder can do about 3 full builds in an hour, so
  in periods where more than 3 commits are landed per hour, it's more likely
  that conitnuous builds will include multiple changes per build and any compile
  failure will necessitate a Findit compile failure analysis and tryjob to find
  a culprit.
  """
  repo_activity = git.CountRecentCommits(
      'https://chromium.googlesource.com/chromium/src.git')
  return repo_activity <= LOW_COMMITS_PER_HOUR


def _PlatformToDimensions(platform):
  """Maps a platform string to the corresponding swarming dimension."""
  return PLATFORM_DIMENSION_MAP[platform]


def _AvailableBotsByPlatform(platform):
  """Returns the bots in findit's pool that are idle and match the platform."""
  dimensions = _PlatformToDimensions(platform)
  dimensions.append('pool:luci.chromium.findit')
  return swarmbot_util.OnlyAvailable(
      swarmbot_util.GetBotsByDimension(dimensions, FinditHttpClient()))


def _PlatformsToBuild():
  """Gets which platforms to build based on available bots and repo activity.

  In periods of low repo activity this function will return the list of
  platforms that have more available bots that running buildaheads, and in other
  times, platforms that have non ongong buildaheads.
  """
  low_repo_activity = _LowRepoActivity()
  result = []
  for platform in BUILD_AHEAD_PLATFORMS:
    platform_jobs = BuildAheadTryJob.RunningJobs(platform)
    if low_repo_activity:
      if len(_AvailableBotsByPlatform(platform)) > len(platform_jobs):
        result.append(platform)
      else:
        logging.info('Not building platform %s as there are fewer available '
                     'bots than running jobs' % platform)
        continue
    elif not platform_jobs:
      result.append(platform)
  return result


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


def UpdateRunningBuilds():
  """Syncs builds in datastore with buildbucket, return ones in progress."""
  result = []
  builds = BuildAheadTryJob.RunningJobs()
  if builds:
    build_ids = [b.BuildId for b in builds]
    updated_builds = buildbucket_client.GetTryJobs(build_ids)
    for error, build in updated_builds:
      if not error:
        if build.status == build.COMPLETED:
          BuildAheadTryJob.Get(build.id).MarkComplete(build.response)
        else:
          result.append(build)
  return result
