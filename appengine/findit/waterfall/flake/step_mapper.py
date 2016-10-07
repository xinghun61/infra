# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

import logging

from common import cache_decorator
from common.http_client_appengine import HttpClientAppengine as HttpClient
from waterfall import buildbot
from waterfall import swarming_util


@cache_decorator.Cached(
    namespace='trybots', cacher=cache_decorator.CompressedMemCacher())
def _LoadTrybots():  # pragma: no cover.
  """Returns the mapping of Commit Queue trybots to Waterfall buildbots."""
  with open(os.path.join(os.path.dirname(__file__), 'trybots.json'), 'r') as f:
    return json.load(f)


def _GetMatchingBuildbots(cq_master_name, cq_builder_name):  # pragma: no cover.
  """Returns a list of matching builder/tester buildbots on Waterfall."""
  trybot_map = _LoadTrybots()
  builders = trybot_map.get(cq_master_name, {}).get('builders', {})
  return builders.get(cq_builder_name, {}).get('bot_ids', [])


def _GetMatchingWaterfallBuildStep(
    cq_build_step, http_client):  # pragma: no cover.
  """Returns the matching Waterfall build step of the given CQ one.

  Args:
    cq_build_step (BuildStep): A build step on Commit Queue.
    http_client (RetryHttpClient): A http client to send http requests.

  Returns:
      (master_name, builder_name, build_number, step_name)
    or
      None
  """
  no_matching_result = (None, None, None, None)

  def GetTagValue(tag_name, tags):
    """Returns the value of a tag in a Swarming task."""
    tag_name_prefix = '%s:' % tag_name
    for tag in tags:
      if tag.startswith(tag_name_prefix):
        return tag[len(tag_name_prefix):]
    return None

  # 1. Map a cq trybot to the matching waterfall buildbots.
  buildbots = _GetMatchingBuildbots(
      cq_build_step.master_name, cq_build_step.builder_name)
  if not buildbots:
    logging.info('%s/%s has no matching Waterfall buildbot',
                  cq_build_step.master_name, cq_build_step.builder_name)
    return no_matching_result  # No matching Waterfall buildbots.

  # 2. Get "name" of the CQ trybot step in the tags of a Swarming task.
  tasks = swarming_util.ListSwarmingTasksDataByTags(
      cq_build_step.master_name, cq_build_step.builder_name,
      cq_build_step.build_number, http_client,
      {'stepname': cq_build_step.step_name})
  if not tasks:
    logging.info(
        '%s/%s/%s is not Swarmed yet.',
        cq_build_step.master_name, cq_build_step.builder_name,
        cq_build_step.step_name)
    return no_matching_result  # Not on Swarm yet.

  # Name of the step in the tags of a Swarming task.
  # Can't use step name, as cq one is with "(with patch)" while waterfall one
  # without.
  name = GetTagValue('name', tasks[0].get('tags', []))
  # The OS in which the test runs on. The same test binary might run on two
  # different OS platforms.
  os_name = GetTagValue('os', tasks[0].get('tags', []))
  if not name or not os_name:
    logging.error(
        'Swarming task has no name/os tag: %s' % tasks[0].get('task_id'))
    return no_matching_result  # No name of the step.

  for bot in buildbots:
    wf_master_name = bot['mastername']
    # Assume Swarmed gtests run on tester bot instead of the builder bot.
    wf_builder_name = bot.get('tester') or bot.get('buildername')
    # TODO: cache and throttle QPS to the same master.
    # 3. Retrieve latest completed build cycle on the buildbot.
    builds = buildbot.GetRecentCompletedBuilds(
        wf_master_name, wf_builder_name, http_client)
    if not builds:
      continue  # No recent builds for the buildbot.

    # 4. Check whether there is matching step.
    # TODO: we might have to check OS or dimension too.
    tasks = swarming_util.ListSwarmingTasksDataByTags(
        wf_master_name, wf_builder_name, builds[0], http_client,
        {'name': name, 'os': os_name})
    if tasks:  # One matching buildbot is found.
      wf_step_name = GetTagValue('stepname', tasks[0].get('tags', []))
      logging.info(
          '%s/%s/%s is mapped to %s/%s/%s',
          cq_build_step.master_name, cq_build_step.builder_name,
          cq_build_step.step_name, wf_master_name, wf_builder_name,
          wf_step_name)
      return wf_master_name, wf_builder_name, builds[0], wf_step_name

  return no_matching_result


def FindMatchingWaterfallStep(build_step):  # pragma: no cover.
  """Finds the matching Waterfall step and checks whether it is supported.

  Only Swarmed and gtest-based steps are supported at the moment.

  Args:
    build_step (BuildStep): A build step on Waterfall or Commit Queue. It
        will be updated with the matching Waterfall step and whether it is
        Swarmed and supported.
  """
  # TODO (chanli): re-implement this hack after step metadata is added.

  build_step.swarmed = False
  build_step.supported = False

  wf_master_name = None
  wf_builder_name = None
  wf_build_number = None
  wf_step_name = None

  http_client = HttpClient()

  if not build_step.master_name.startswith('tryserver.'):
    wf_master_name = build_step.master_name
    wf_builder_name = build_step.builder_name
    wf_build_number = build_step.build_number
    wf_step_name = build_step.step_name
  else:
    step_info = _GetMatchingWaterfallBuildStep(build_step, http_client)
    wf_master_name, wf_builder_name, wf_build_number, wf_step_name = step_info

  build_step.wf_master_name = wf_master_name
  build_step.wf_builder_name = wf_builder_name
  build_step.wf_build_number = wf_build_number
  build_step.wf_step_name = wf_step_name

  if not build_step.has_matching_waterfall_step:
    return

  # Query Swarming for isolated data.
  step_isolated_data = swarming_util.GetIsolatedDataForStep(
      build_step.master_name, build_step.builder_name, build_step.build_number,
      build_step.step_name, http_client)
  build_step.swarmed = len(step_isolated_data) > 0

  if build_step.swarmed:
    # Retrieve a sample output from Isolate.
    output = swarming_util.RetrieveShardedTestResultsFromIsolatedServer(
        step_isolated_data[:1], http_client)
    if output:
      # Guess from the format.
      build_step.supported = (
          isinstance(output, dict) and
          isinstance(output.get('all_tests'), list) and
          isinstance(output.get('per_iteration_data'), list) and
          all(isinstance(i, dict) for i in output.get('per_iteration_data'))
      )
