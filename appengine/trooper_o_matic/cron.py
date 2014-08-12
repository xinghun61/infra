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
import re
import urllib
import webapp2

from google.appengine.api import urlfetch

import models
import trees


def datetime_now():
  """Easy to mock datetime.datetime.now() for unit testing."""
  return datetime.datetime.now()

def date_from_str(string, base_format):
  """Converts a string to a date, taking into account the possible existence
     of a millisecond precision value."""
  try:
    return datetime.datetime.strptime(string, base_format + '.%f')
  except ValueError:
    return datetime.datetime.strptime(string, base_format)

class CheckCqHandler(webapp2.RequestHandler):
  """Collect commit queue length and run times."""

  pending_api_url = 'https://chromium-commit-queue.appspot.com/api/%s/pending'
  rietveld_api_url = ('https://codereview.chromium.org/search?format=json'
                      '&limit=500&with_messages=1&order=modified'
                      '&modified_after=%s')
  start_regexp = re.compile(
      r'CQ is trying da patch.*( |/)(?P<author>.*)/(?P<issue_id>\d+)/'
      r'(?P<patch_id>\d+)$', re.DOTALL)
  committed_regexp = re.compile(r'Change committed as (?P<revision>\d+)')
  manual_commit_regexp = re.compile(
      r'Committed patchset #(?P<patch_id>\d+) manually as r(?P<revision>\d+)')

  @staticmethod
  def date_from_iso_str(iso_str):
    """Convert the date from a rietveld message into a datetime.

    Args:
        iso_str: string datetime from rietveld message. These have one of two
                 formats:
                 2013-10-17 16:43:04.391480
                 2013-10-17 16:43:04

    Returns:
        datetime.datetime
    """
    return date_from_str(iso_str, '%Y-%m-%d %H:%M:%S')

  @staticmethod
  def record_cq_time(time, cutoff, run_info, runs, result, msg_text, issue):
    if not run_info:
      logging.error('Missing CQ start message for end message %s on issue %s',
                    msg_text, issue)
      return
    if time < cutoff:
      return
    run_info['end'] = time
    delta = run_info['end'] - run_info['start']
    run_info['minutes'] = int(delta.total_seconds() / 60)
    run_info['result'] = result
    runs.append(run_info)

  def get(self):
    # We only care about the last hour.
    cutoff = datetime_now() - datetime.timedelta(hours=1)
    modified_after = urllib.quote(cutoff.strftime('%Y-%m-%d %H:%M:%S'))

    # Rietveld has a limit of 1000 results it can return, and if there are more
    # results it will return a cursor. So loop through results until
    # there is no cursor.
    cursor = None
    more_results = True
    issues = []
    while more_results:
      url = self.rietveld_api_url % modified_after
      if cursor:
        url = url + '&cursor=' + cursor
      result = urlfetch.fetch(url=url, deadline=60)
      content = json.loads(result.content)
      new_issues = content['results']
      issues += new_issues
      cursor = content.get('cursor')
      more_results = new_issues and cursor

    # Only track the chromium and blink projects. Split them out here because
    # the project= field in the rietveld API does not work.
    # TODO(sullivan): if CQ exposes its projects as an API, use it here instead
    # of hard-coding.
    projects = set(['chromium', 'blink'])
    cq_issues = {
        'chromium': [i for i in issues if i['project'] == 'chromium'],
        'blink': [i for i in issues if i['project'] == 'blink'],
    }
    for project in projects:
      # Ensure there is an ancestor for all the stats for this project.
      project_model = models.Project.get_or_insert(project)
      project_model.put()
      stat = models.CqStat(parent=project_model.key)

      # CQ exposes an API for its length.
      result = urlfetch.fetch(url=self.pending_api_url % project, deadline=60)
      pending = set(json.loads(result.content)['results'])
      stat.length = len(pending)
      cq_runs = []

      # Getting the running time is more complicated. Loop through each issue,
      # parsing the commit queue messages to find start and end times for CQ
      # attempts. Only count finished runs. This is similar to the
      # implementation at http://go/stats.py except we only count times of
      # individual runs, instead of summing retries together.
      for issue in cq_issues[project]:
        current_run = None
        for msg in issue['messages']:
          if msg['sender'] != 'commit-bot@chromium.org':
            continue
          text = msg['text']
          date = self.date_from_iso_str(msg['date'])

          match = self.start_regexp.match(text)
          if match:
            patch_id = match.group('patch_id')
            current_run = {
                'patch_id': patch_id,
                'issue_id': issue['issue'],
                'start': date,
            }
            continue

          if (self.committed_regexp.match(text) or
              text.startswith('This issue passed the CQ.')):
            self.record_cq_time(date, cutoff, current_run, cq_runs,
                                'COMMITTED', text, issue['issue'])
            current_run = None

          cq_end_messages = {
              'TRY': 'Retried try job',
              'TRY_JOBS_FAILED': 'Try jobs failed on following builders',
              'APPLY': 'Failed to apply patch',
              'APPLY2': 'Failed to apply the patch',
              'BAD_SVN': 'Could not make sense out of svn commit message',
              'COMPILE': 'Sorry for I got bad news for ya',
              'DESCRIPTION_CHANGED': ('Commit queue rejected this change'
                                      ' because the description'),
              # This is too conservative.
              'REVIEWERS_CHANGED': 'List of reviewers changed.',
              # User caused.
              'PATCH_CHANGED': 'Commit queue failed due to new patchset.',
              # FAILED_TO_TRIGGER is a very serious failure, unclear why it
              # happens!
              'FAILED_TO_TRIGGER': 'Failed to trigger a try job on',
              # BINARY_FILE is just a bug in the CQ.
              'BINARY_FILE': 'Can\'t process patch for file',
              'BINARY_FILE2': 'Failed to request the patch to try',
              # Unclear why UPDATE_STEP happens.  Likely broken bots, shouldn't
              # fail patches!
              'UPDATE_STEP': 'Step "update" is always a major failure.',
              'BERSERK': 'The commit queue went berserk',
              'INTERNAL_ERROR': 'Commit queue had an internal error.',
          }
          for result, message_text in cq_end_messages.items():
            if text.startswith(message_text):
              self.record_cq_time(date, cutoff, current_run, cq_runs,
                                  result, text, issue['issue'])
              current_run = None
              break

      if cq_runs:
        minutes = sorted([item['minutes'] for item in cq_runs])
        stat.min = minutes[0]
        stat.max = minutes[-1]
        stat.mean = numpy.mean(minutes)
        stat.p10 = numpy.percentile(minutes, 10)
        stat.p25 = numpy.percentile(minutes, 25)
        stat.p50 = numpy.percentile(minutes, 50)
        stat.p75 = numpy.percentile(minutes, 75)
        stat.p90 = numpy.percentile(minutes, 90)
        stat.p95 = numpy.percentile(minutes, 95)
        stat.p99 = numpy.percentile(minutes, 99)
      stat.put()


class CheckTreeHandler(webapp2.RequestHandler):
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
                                      revision=int(record['revision']))
          stat.slo_offenders.append(v)
          if record['step_time'] > models.SLO_BUILDTIME_MAX:
            stat.num_over_max_slo += 1
    stat.put()


class CheckTreeStatusHandler(webapp2.RequestHandler):

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

  def fetchEntries(self, project, days):
    # Get two previous days of data, in case the tree has been in the same
    # state for the entire time period.
    data_start = datetime_now() - datetime.timedelta(days=days+2)
    url = self.status_url % (project, calendar.timegm(data_start.timetuple()))
    result = urlfetch.fetch(url)
    entries = json.loads(result.content)
    entries.sort(key=self.date_for)
    return entries

  def getStateOfTree(self, entries, cutoff):
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

    entries = self.fetchEntries(project, days)
    was_open = self.getStateOfTree(entries, cutoff)

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
