# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Handler for comparing the performance of tryjobs on swarming-backed bots."""

import logging

from datetime import datetime
from datetime import timedelta

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model.flake.flake_try_job_data import FlakeTryJobData
from model.wf_config import FinditConfig
from model.wf_try_job_data import WfTryJobData


def _GetStartEndDates(start, end):
  """Return the specified dates if both are correctly formatted.

  Otherwise use the last 30 days as the interval.
  """
  if start and end:
    try:
      start = datetime.strptime(start, '%Y-%m-%d')
      end = datetime.strptime(end, '%Y-%m-%d')
      return min(start, end), max(start, end)
    except (ValueError, TypeError):
      pass
  default_end = time_util.GetUTCNow()
  default_start = default_end - timedelta(days=30)
  return default_start, default_end


def _GetSwarmbucketBuilders():
  """Find bots that are available on swarming and buildbot.

  Returns:
    A dictionary that maps swarming builders like
    'luci.chromium.try/linux_variable' to buildbot builders like
    'tryserver.chromium.linux/linux_variable'
  """
  results = {}
  all_bots = FinditConfig().Get().builders_to_trybots
  for waterfall_master in all_bots:
    for waterfall_builder in all_bots[waterfall_master]:
      bot = all_bots[waterfall_master][waterfall_builder]
      swarming_master = bot.get('swarmbucket_mastername')
      swarming_bot = bot.get('swarmbucket_trybot')
      buildbot_master = bot.get('mastername')
      buildbot_bot = bot.get('waterfall_trybot')
      if swarming_master and swarming_bot and buildbot_master and buildbot_bot:
        results['%s/%s' % (swarming_master,
                           swarming_bot)] = '%s/%s' % (buildbot_master,
                                                       buildbot_bot)
  return results


def _GetBotFromBuildbucketResponse(response):
  #TODO(move this to buildbucket_client.py or where appropriate.
  master = response['bucket']
  master = master[len('master.'):] if master.startswith('master.') else master
  for tag in response['tags']:
    if ':' in tag:
      k, v = tag.split(':', 1)
      if k == 'builder':
        return '%s/%s' % (master, v)
  logging.exception('Buildbucket response does not specify a builder tag')
  return None


def _FindRecentSwarmbucketJobs(start, end, builders):
  start_date, end_date = _GetStartEndDates(start, end)

  wf_try_job_query = WfTryJobData.query(WfTryJobData.created_time >= start_date,
                                        WfTryJobData.created_time < end_date)
  flake_try_job_query = FlakeTryJobData.query(
      FlakeTryJobData.created_time >= start_date,
      FlakeTryJobData.created_time < end_date)
  try_job_data_list = wf_try_job_query.fetch() + flake_try_job_query.fetch()

  # Find recent swarmbucket tryjobs.
  relevant_try_job_data = []
  for try_job_data in try_job_data_list:
    this_builder = _GetBotFromBuildbucketResponse(
        try_job_data.last_buildbucket_response)
    if this_builder in builders:
      relevant_try_job_data.append({
          'try_job_data': try_job_data,
          'builder': this_builder
      })
  return relevant_try_job_data


def _FindJobPairs(recent_jobs, swarmbucket_builders):
  """Search the try job entity for runs of the same job on buildbot.

  Args:
    recent_jobs (list): A list of try_job_data entities for swarmbucket runs.

  Returns:
    A list of pairs, where the first item of each pair will be the try_job_data
    entity taken from the input, and the second will be the try_job_data entity
    for the same job but run on buildbot, or None if no such job exists.
  """
  results = []
  for item in recent_jobs:
    try_job_data = item['try_job_data']
    builder = item['builder']
    matching_job_found = False
    try_job = try_job_data.try_job_key.get()
    for build_id in try_job.try_job_ids:
      other_try_job_data = WfTryJobData.Get(build_id)
      other_builder = _GetBotFromBuildbucketResponse(
          other_try_job_data.last_buildbucket_response)
      if builder and swarmbucket_builders[builder] == other_builder:
        results.append((try_job_data, other_try_job_data))
        matching_job_found = True
        break

    if not matching_job_found:
      results.append((try_job_data, None))
  return results


def _FormatRows(pairs):
  result = []
  for pair in pairs:
    row_data = {}
    swarmbucket_job, buildbot_job = pair
    row_data['swarmbucket_builder'] = _GetBotFromBuildbucketResponse(
        swarmbucket_job.last_buildbucket_response)
    row_data['swarmbucket_try_job_id'] = swarmbucket_job.key.pairs()[0][1]
    row_data['swarmbucket_try_job_url'] = swarmbucket_job.try_job_url
    row_data['swarmbucket_completion_date'] = time_util.FormatDatetime(
        swarmbucket_job.end_time)
    if not swarmbucket_job.error_code and swarmbucket_job.end_time:
      row_data['swarmbucket_run_time'] = (
          swarmbucket_job.end_time -
          swarmbucket_job.start_time).total_seconds()
    if buildbot_job:
      row_data['buildbot_builder'] = _GetBotFromBuildbucketResponse(
          buildbot_job.last_buildbucket_response)
      row_data['buildbot_try_job_id'] = buildbot_job.key.pairs()[0][1]
      row_data['buildbot_try_job_url'] = buildbot_job.try_job_url
      row_data['buildbot_completion_date'] = time_util.FormatDatetime(
          buildbot_job.end_time)
      if not buildbot_job.error_code and buildbot_job.end_time:
        row_data['buildbot_run_time'] = (
            buildbot_job.end_time - buildbot_job.start_time).total_seconds()
    result.append(row_data)
  return result


class SwarmbucketPerformance(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):
    swarmbucket_builders = _GetSwarmbucketBuilders()
    recent_jobs = _FindRecentSwarmbucketJobs(
        self.request.get('start_date'),
        self.request.get('end_date'), swarmbucket_builders)

    jobs = _FormatRows(_FindJobPairs(recent_jobs, swarmbucket_builders))

    use_json = self.request.get('format') == 'json'
    response = {} if use_json else {'template': 'swarmbucket_performance.html'}
    response['data'] = {'jobs': jobs}
    return response
