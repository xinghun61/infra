# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Collect stats regularly via app engine cron.
"""

import calendar
import datetime
import json
import logging

import numpy
import webapp2

from google.appengine.api import urlfetch

import models
import trees


def datetime_now():  # pragma: no cover
  """Easy to mock datetime.datetime.utcnow() for unit testing."""
  return datetime.datetime.utcnow()


def date_from_str(string, base_format):  # pragma: no cover
  """Converts a string to a date, taking into account the possible existence
     of a millisecond precision value."""
  try:
    return datetime.datetime.strptime(string, base_format + '.%f')
  except ValueError:
    return datetime.datetime.strptime(string, base_format)


class CheckCqHandler(webapp2.RequestHandler):  # pragma: no cover
  """Collect commit queue length and run times."""

  patch_stop_list = ('http://chromium-cq-status.appspot.com/query/action='
                     'patch_stop/?begin=%d')

  pending_api_url = 'https://chromium-commit-queue.appspot.com/api/%s/pending'

  patchset_details = ('https://chromium-cq-status.appspot.com/query/'
                      'issue=%d/patchset=%d/')

  @staticmethod
  def update_stat_for_times(stat, times):
    stat.min = times[0]
    stat.max = times[-1]
    stat.mean = numpy.mean(times)
    stat.p10 = numpy.percentile(times, 10)
    stat.p25 = numpy.percentile(times, 25)
    stat.p50 = numpy.percentile(times, 50)
    stat.p75 = numpy.percentile(times, 75)
    stat.p90 = numpy.percentile(times, 90)
    stat.p95 = numpy.percentile(times, 95)
    stat.p99 = numpy.percentile(times, 99)

  def get(self):
    # We only care about the last hour.
    cutoff = datetime_now() - datetime.timedelta(hours=1)
    url = self.patch_stop_list % calendar.timegm(
        cutoff.timetuple())

    # CQ API has a limit of results it will return, and if there are more
    # results it will return a cursor. So loop through results until
    # there is no cursor.
    cursor = None
    more_results = True
    patchsets = {}
    while more_results:
      if cursor:
        url = url + '&cursor=' + cursor
      result = urlfetch.fetch(url=url, deadline=60)
      content = json.loads(result.content)
      for result in content['results']:
        patchsets.setdefault(result['fields']['project'], set()).add(
            (result['fields']['issue'], result['fields']['patchset']))
      cursor = content.get('cursor')
      more_results = content.get('more')

    # Only track the chromium and blink projects.
    projects = set(['chromium', 'blink'])
    for project in projects:
      # Ensure there is an ancestor for all the stats for this project.
      project_model = models.Project.get_or_insert(project)
      project_model.put()

      # CQ exposes an API for its length.
      result = urlfetch.fetch(url=self.pending_api_url % project, deadline=60)
      pending = set(json.loads(result.content)['results'])
      num_pending = len(pending)
      stat = models.CqStat(parent=project_model.key, length=num_pending)
      patch_in_queue_stat = models.CqTimeInQueueForPatchStat(
          parent=project_model.key, length=num_pending)
      patch_total_time_stat = models.CqTotalTimeForPatchStat(
          parent=project_model.key, length=num_pending)

      single_run_times = []
      in_queue_times = []
      total_times = []

      for patchset in patchsets[project]:
        url = self.patchset_details % (patchset[0], patchset[1])
        result = urlfetch.fetch(url=url, deadline=60)
        content = json.loads(result.content)
        # Get a list of all starts/stops for this patch.
        actions = [result['fields'] for result in content['results'] if (
            result['fields'].get('action') == 'patch_start' or
            result['fields'].get('action') == 'patch_stop')]
        actions.sort(key=lambda k: k['timestamp'])

        start_time = None
        last_start = None
        end_time = None
        run_times = []
        for action in actions:
          if action['action'] == 'patch_start':
            if not start_time:
              start_time = action['timestamp']
            last_start = action['timestamp']
          else:
            if last_start:
              run_time = (action['timestamp'] - last_start) / 60
              run_times.append(run_time)
              last_start = None
              end_time = action['timestamp']

        if run_times:
          single_run_times += run_times
          in_queue_times.append(sum(run_times))
          total_times.append((end_time - start_time) / 60)

      if single_run_times:
        self.update_stat_for_times(stat, sorted(single_run_times))
        self.update_stat_for_times(patch_in_queue_stat, sorted(in_queue_times))
        self.update_stat_for_times(patch_total_time_stat, sorted(total_times))

      stat.put()
      patch_in_queue_stat.put()
      patch_total_time_stat.put()


class CheckTreeHandler(webapp2.RequestHandler): # pragma: no cover
  """Checks the given tree for build times higher than the SLO specifies."""

  stats_api_url = ('https://chrome-infra-stats.appspot.com/_ah/api/stats/v1/'
                   'steps/%s/overall__build__result__/%s')

  last_hour_format = '%Y-%m-%dT%H:%MZ'
  generated_format = '%Y-%m-%dT%H:%M:%S'

  def get(self, tree):
    """For each master in the tree, find builds that don't meet our SLO."""
    masters = trees.GetMastersForTree(tree)
    if not masters:
      logging.error('Invalid tree %s', tree)
      return
    now = datetime_now()
    tree_model = models.Tree.get_or_insert(tree)
    tree_model.put()
    stat = models.BuildTimeStat(parent=tree_model.key,
                                timestamp=now,
                                num_builds=0,
                                num_over_median_slo=0,
                                num_over_max_slo=0)
    # The chrome-infra-stats API lists builds that have STARTED in the last
    # hour. We want to list builds that have ENDED in the last hour, so we need
    # to go back through the last 24 hours to make sure we don't miss any.
    # TODO(sullivan): When an "ended in last hour" API is available, switch
    # to that.
    hours = [now - datetime.timedelta(hours=h) for h in range(0, 24)]
    hour_strs = [hour.strftime(self.last_hour_format) for hour in hours]
    last_hour = datetime.timedelta(hours=1)
    for master in masters:
      records = []
      urls = [self.stats_api_url % (master, hour_str) for hour_str in hour_strs]
      for url in urls:
        logging.info(url)
        result = urlfetch.fetch(url=url, deadline=60)
        content = json.loads(result.content)
        records += content.get('step_records', [])
      for record in records:
        generated_time = date_from_str(record['generated'],
                                       self.generated_format)
        if now - generated_time > last_hour:
          continue
        stat.num_builds += 1
        if record['step_time'] > models.SLO_BUILDTIME_MEDIAN:
          stat.num_over_median_slo += 1
          v = models.BuildSLOOffender(tree=tree, master=master,
                                      builder=record['builder'],
                                      buildnumber=int(record['buildnumber']),
                                      buildtime=float(record['step_time']),
                                      result=int(record['result']),
                                      revision=record['revision'])
          stat.slo_offenders.append(v)
          if record['step_time'] > models.SLO_BUILDTIME_MAX:
            stat.num_over_max_slo += 1
    stat.put()


class CheckTreeStatusHandler(webapp2.RequestHandler): # pragma: no cover

  status_url = ('https://%s-status.appspot.com/allstatus?format=json&'
                'endTime=%s&limit=1000')

  @staticmethod
  def tree_is_open_for(entry):
    # Count scheduled maintenance as tree open, we only want to alert on
    # unexpected closures.
    return (entry['can_commit_freely'] or
            entry['message'].startswith('Tree is closed for maintenance'))

  @staticmethod
  def date_for( entry):
    return datetime.datetime.strptime(entry['date'], '%Y-%m-%d %H:%M:%S.%f')

  def fetch_entries(self, project, days):
    # Get two previous days of data, in case the tree has been in the same
    # state for the entire time period.
    data_start = datetime_now() - datetime.timedelta(days=days+2)
    url = self.status_url % (project, calendar.timegm(data_start.timetuple()))
    result = urlfetch.fetch(url)
    entries = json.loads(result.content)
    entries.sort(key=self.date_for)
    return entries

  def get_state_of_tree(self, entries, cutoff):
    # Find the state of the tree before the days started.
    was_open = True
    for _, entry in enumerate(entries):
      if self.date_for(entry) > cutoff:
        break
      was_open = self.tree_is_open_for(entry)
    return was_open

  def get(self, project, days):
    # Check tree status in last N days
    days = int(days)
    now = datetime_now()
    cutoff = datetime_now() - datetime.timedelta(days=days)

    entries = self.fetch_entries(project, days)
    was_open = self.get_state_of_tree(entries, cutoff)

    # Now look through the entries in the relevant days to find the tree open
    # times.
    last_change = cutoff
    open_time = datetime.timedelta(seconds=0)
    closed_time = datetime.timedelta(seconds=0)
    for entry in entries:
      is_open = self.tree_is_open_for(entry)
      if self.date_for(entry) <= cutoff or is_open == was_open:
        continue
      current_time = self.date_for(entry)
      delta = current_time - last_change
      if was_open:
        open_time += delta
      else:
        closed_time += delta
      last_change = current_time
      was_open = is_open

    delta = now - last_change
    if was_open:
      open_time += delta
    else:
      closed_time += delta

    open_seconds = open_time.total_seconds()
    closed_seconds = closed_time.total_seconds()
    project_model = models.Project.get_or_insert(project)
    project_model.put()
    stat = models.TreeOpenStat(
        parent=project_model.key,
        num_days=days,
        percent_open=(open_seconds / (open_seconds + closed_seconds)) * 100)
    stat.put()
