# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module includes swarmbot related logic."""

import hashlib
import json
import logging

from common.waterfall import buildbucket_client
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from infra_api_clients import http_client_util
from infra_api_clients.swarming import swarming_util
from model.wf_try_bot_cache import WfTryBot
from model.wf_try_bot_cache import WfTryBotCache
from services import constants
from services import swarming
from services.flake_failure import flake_constants

# Swarming URL templates.
BOT_LIST_URL = 'https://%s/_ah/api/swarming/v1/bots/list%s'


def GetCacheName(master, builder, suffix=""):
  hash_part = hashlib.sha256('%s:%s' % (master, builder)).hexdigest()
  result = 'builder_%s' % hash_part
  if suffix:
    result = '%s_%s' % (result, suffix)
  return result


def GetBot(build):
  """Parses the swarming bot from the buildbucket response"""
  assert build
  if build.response:
    details = json.loads(build.response.get('result_details_json', '{}'))
    if details:
      return details.get('swarming', {}).get('task_result', {}).get('bot_id')
  return None


def GetBuilderCacheName(build):
  """Gets the named cache's name from the buildbucket response"""
  assert build
  parameters = json.loads(build.response.get('parameters_json', '{}'))
  if parameters:
    swarming_params = parameters.get('swarming', {}).get(
        'override_builder_cfg', {})
    for cache in swarming_params.get('caches', []):
      if cache.get('path') == 'builder':
        return cache.get('name')
  return None


def GetBotsByDimension(dimensions, http_client):
  url = BOT_LIST_URL % (swarming.SwarmingHost(),
                        swarming_util.ParametersToQueryString(
                            dimensions, 'dimensions'))

  content, error = http_client_util.SendRequestToServer(url, http_client)
  if error:
    logging.error(
        'failed to list bots by dimension with %s, falling back to '
        'any selecting any bot', error)
    return []

  if not content:
    logging.warning('got blank response from %s', url)
    return []

  content_data = json.loads(content)
  return content_data.get('items', [])


def GetAllBotsWithCache(dimensions, cache_name, http_client):
  dimensions['caches'] = cache_name
  return GetBotsByDimension(dimensions, http_client)


def OnlyAvailable(bots):
  return [
      b for b in bots if not (b.get('task_id') or b.get('is_dead') or
                              b.get('quarantined') or b.get('deleted'))
  ]


def _HaveCommitPositionInLocalGitCache(bots, commit_position):
  result = []
  for b in bots:
    bot_id = b.get('bot_id')
    if WfTryBot.Get(bot_id).newest_synced_revision >= commit_position:
      result.append(b)
  return result


def _SortByDistanceToCommitPosition(bots, cache_name, commit_position,
                                    include_later):
  cache_stats = WfTryBotCache.Get(cache_name)

  def _distance(bot_id):
    # If the bot is new, the bot_id will not be present, but if it failed to get
    # the revision, the key will be present with a value of None.
    local_cp = cache_stats.checked_out_commit_positions.get(bot_id) or 0
    return commit_position - local_cp

  if include_later:
    distance = lambda x: abs(_distance(x))
  else:
    distance = _distance
  result = sorted(
      [b for b in bots if distance(b['bot_id']) >= 0],
      key=lambda x: distance(x['bot_id']))
  return result


def _ClosestEarlier(bots, cache_name, commit_position):
  result = _SortByDistanceToCommitPosition(bots, cache_name, commit_position,
                                           False)
  return result[0] if result else None


def _ClosestLater(bots, cache_name, commit_position):
  result = _SortByDistanceToCommitPosition(bots, cache_name, commit_position,
                                           True)
  return result[0] if result else None


def _GetBotWithFewestNamedCaches(bots):
  """Selects the bot that has the fewest named caches.

  To break ties, the bot with the most available disk space is selected.

  Args:
    bots(list): A list of bot dicts as returned by the swarming.bots.list api
      with a minimum length of 1.

  Returns:
    One bot from the list.
  """
  # This list will contain a triplet (cache_count, -free_space, bot) for each
  # bot.
  candidates = []
  for b in bots:
    try:
      caches_dimension = [
          d['value'] for d in b['dimensions'] if d['key'] == 'caches'
      ][0]
      # We only care about caches whose name starts with 'builder_' as that is
      # the convention that we use in GetCacheName.
      cache_count = len(
          [cache for cache in caches_dimension if cache.startswith('builder_')])
      bot_state = json.loads(b['state'])
      free_space = sum(
          [disk['free_mb'] for _, disk in bot_state['disks'].iteritems()])
    except (KeyError, TypeError, ValueError):
      # If we can't determine the values, we add the bot to the end of the list.
      candidates.append((1000, 0, b))
    else:
      # We use negative free space in this triplet so that a single sort will
      # put the one with the most free space first if there is a tie in cache
      # count with a single sort.
      candidates.append((cache_count, -free_space, b))
  return sorted(candidates)[0][2]


def AssignWarmCacheHost(tryjob, cache_name, http_client):
  """Selects the best possible slave for a given tryjob.

  We try to get as many of the following conditions as possible:
   - The bot is available,
   - The bot has the named cached requested by the tryjob,
   - The revision to test has already been fetched to the bot's local git cache,
   - The currently checked out revision at the named cache is the closest
     to the revision to test, and if possible it's earlier to it (so that
     bot_update only moves forward, preferably)
  If a match is found, it is added to the tryjob parameter as a dimension.

  Args:
    tryjob (buildbucket_client.TryJob): The ready-to-be-scheduled job.
    cache_name (str): Previously computed name of the cache to match the
        referred build's builder and master.
    http_client: http_client to use for swarming and gitiles requests.
  """
  if not tryjob.is_swarmbucket_build:
    return
  request_dimensions = dict([x.split(':', 1) for x in tryjob.dimensions])
  bots_with_cache = OnlyAvailable(
      GetAllBotsWithCache(request_dimensions, cache_name, http_client))

  if bots_with_cache:

    # Flake tryjobs check out older code, so there's little benefit in trying to
    # optimize the way we do for non-flake tryjobs, we do however select the bot
    # with the fewest named caches in an effort to avoid unnecessary cache
    # evictions.
    if cache_name and cache_name.endswith(flake_constants.FLAKE_CACHE_SUFFIX):
      selected_bot = _GetBotWithFewestNamedCaches(bots_with_cache)['bot_id']
      tryjob.dimensions.append('id:%s' % selected_bot)
      return

    git_repo = CachedGitilesRepository(http_client,
                                       constants.CHROMIUM_GIT_REPOSITORY_URL)
    # TODO(crbug.com/800107): Pass revision as a parameter.
    revision = (
        tryjob.properties.get('bad_revision') or
        tryjob.properties.get('test_revision'))
    if not revision:
      logging.error('Tryjob %s does not have a specified revision.' % tryjob)
      return
    target_commit_position = git_repo.GetChangeLog(revision).commit_position

    bots_with_rev = _HaveCommitPositionInLocalGitCache(bots_with_cache,
                                                       target_commit_position)
    if not bots_with_rev:
      selected_bot = _GetBotWithFewestNamedCaches(bots_with_cache)['bot_id']
      tryjob.dimensions.append('id:' + selected_bot)
      return

    bots_with_latest_earlier_rev_checked_out = _ClosestEarlier(
        bots_with_rev, cache_name, target_commit_position)
    if bots_with_latest_earlier_rev_checked_out:
      tryjob.dimensions.append(
          'id:' + bots_with_latest_earlier_rev_checked_out['bot_id'])
      return

    bots_with_earliest_later_rev_checked_out = _ClosestLater(
        bots_with_rev, cache_name, target_commit_position)
    if bots_with_earliest_later_rev_checked_out:
      tryjob.dimensions.append(
          'id:' + bots_with_earliest_later_rev_checked_out['bot_id'])
      return

    selected_bot = _GetBotWithFewestNamedCaches(bots_with_rev)['bot_id']
    tryjob.dimensions.append('id:' + selected_bot)
    return

  else:
    idle_bots = OnlyAvailable(
        GetBotsByDimension(request_dimensions, http_client))
    if idle_bots:
      selected_bot = _GetBotWithFewestNamedCaches(idle_bots)['bot_id']
      tryjob.dimensions.append('id:' + selected_bot)
