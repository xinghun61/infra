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
from model.wf_try_bot_cache import WfTryBotCache
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

# How many commit positions it takes for the copy of a cache to be considered
# stale.
STALE_CACHE_AGE = 1000  # Nice round number, usually less than a week.


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
  return PLATFORM_DIMENSION_MAP[platform][:]


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


def _PickRandomBuilder(builders):
  """Randomly select one builder to do a full build for.

  This selects one of the builders and uses the relative age of the newest build
  (in revisions) for each cache as its weight for random selection, favoring the
  caches that are older.
  """
  for b in builders:
    b['newest_build'] = max(
        b['cache_stats'].full_build_commit_positions.values() or [0])
  newest_build = max([b['newest_build'] for b in builders])
  for b in builders:
    b['cache_age'] = newest_build - b['newest_build']

  # Weighted random selection
  weight_sum = sum(b['cache_age'] for b in builders)
  r = random.uniform(0, weight_sum)
  for b in builders:  # pragma: no branch
    if r <= b['cache_age']:
      return b
    r -= b['cache_age']


def _GetSupportedCompileCaches(platform):
  """Gets config'd compile builders by platform & their cache name and stats."""
  builders = waterfall_config.GetSupportedCompileBuilders(platform)
  for builder in builders:
    # It is OK to use the master and builder directly instead of looking for a
    # parent, because GetSupportedCompileBuilders filters out test builders,
    # which are the ones that have parent builders.
    builder['cache_name'] = swarmbot_util.GetCacheName(builder['master'],
                                                       builder['builder'])
    builder['cache_stats'] = WfTryBotCache.Get(builder['cache_name'])
  return builders


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
  if bot:
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


def _TreeIsOpen():
  """Determine whether the chromium tree is currently open."""
  url = 'https://chromium-status.appspot.com/allstatus'
  params = {
      'limit': '1',
      'format': 'json',
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


def _UpdateRunningBuilds():
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


def _TriggerAndSave(master, builder, cache_name, platform, bot):
  """Starts a new build ahead try job on the specified bot and saves it to ndb.

  Args:
    master (str): Waterfall master which config to match.
    builder (str): Waterfall builder which config to match.
    cache_name (str): The cache name used by tryjobs intended to match the
        master/builder combo above.
    platform (str): Platform for the master/builder combo.
    bot (str): The `id` dimension of bot selected to do the build. None to
        let swarming pick the bot.

  Returns:
    The BuildAheadTryJobEntity.
  """
  error, build = TriggerBuildAhead(master, builder, bot)
  if error:
    raise Exception(error)
  build_ahead = BuildAheadTryJob.Create(build.id, platform, cache_name)
  build_ahead.put()
  return build_ahead


def _OldEnough(try_bot_cache, bot_id):
  """Checks if the build in the given bot's cache is older than threshold."""
  built_cp = try_bot_cache.full_build_commit_positions[bot_id]
  tot_cp = git.GetCLInfo(['HEAD']).get('HEAD', {}).get('commit_position')
  return built_cp < tot_cp - STALE_CACHE_AGE


def _StartBuildAhead(platform):
  """Chooses a target builder for the given platform and starts a build.

  It also tries to choose which bot to do the build on based on the number of
  available bots that have a copy of the cache and the relative age of their
  latest full builds.

  Returns:
    A BuildAheadTryJob entity. In certain conditions it skips triggering a
    build, and in those cases it returns None.
  """
  supported_builders = _GetSupportedCompileCaches(platform)
  if not supported_builders:
    return None
  chosen_builder = _PickRandomBuilder(supported_builders)
  try_bot_cache = chosen_builder['cache_stats']
  master = chosen_builder['master']
  builder = chosen_builder['builder']
  cache_name = chosen_builder['cache_name']

  bot_ids_with_cache = try_bot_cache.full_build_commit_positions.keys()
  available_bots = _AvailableBotsByPlatform(platform)
  available_bot_ids_with_cache = [
      b for b in bot_ids_with_cache if b in set(
          ab.get('bot_id') for ab in available_bots)
  ]
  if len(available_bot_ids_with_cache) >= 2:
    # Select the second newest one, we want the newest cache to remain available
    # for a possible compile tryjob.
    bot_id = sorted(
        available_bot_ids_with_cache,
        key=lambda b: try_bot_cache.full_build_commit_positions[b],
        reverse=True)[1]
  elif not available_bot_ids_with_cache:
    # Let swarming pick the bot.
    bot_id = None
  elif _OldEnough(try_bot_cache, available_bot_ids_with_cache[0]):
    # Rebuild the only available cache (it's likely too old to save significant
    # time).
    bot_id = available_bot_ids_with_cache[0]
  else:
    # Do nothing, because the available cache is new enough to be useful as is,
    # compared to the risk of forcing a build from scratch if we block it while
    # we rebuild.
    return None
  return _TriggerAndSave(master, builder, cache_name, platform, bot_id)


def BuildCaches():
  """Entry point for the logic that builds caches ahead of need.

  Its three main stages are:
    - Update the status of ongoing build aheads.
    - Decide which platforms to trigger based on repo activity and pool usage.
    - Trigger jobs on the selected platforms.
  """
  _UpdateRunningBuilds()
  if _TreeIsOpen():
    for platform in _PlatformsToBuild():
      _StartBuildAhead(platform)
