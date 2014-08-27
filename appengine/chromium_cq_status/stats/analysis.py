# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta
import logging
import math

from model.cq_stats import ( # pylint: disable-msg=E0611
  CountStats,
  CQStats,
  ListStats,
)
from model.record import Record # pylint: disable-msg=E0611
from shared.config import STATS_START_TIMESTAMP
from stats import patchset_stats, tryjobverifier_stats

start_tag = 'action=patch_start'
stop_tag = 'action=patch_stop'
project_tag = 'project=%s'
issue_tag = 'issue=%s'
patchset_tag = 'patchset=%s'

utcnow_for_testing = None

# Functions that take a {(issue, patchset): [[Record]]}
# and return a CountStats or ListStats.
analyzer_lists = (
  patchset_stats.analyzers(),
  tryjobverifier_stats.analyzers(),
)

def analyze_interval(days): # pragma: no cover
  """Build and save CQStats for every <days> interval in Records.

  Walks forwards through the Records history <days> at a time,
  analyzing and saving CQStats for each interval.
  """
  if Record.query().count(1) == 0:
    return
  logging.debug('Analyzing records %s days at a time' % days)
  begin, end = next_stats_interval(days)
  while end < (utcnow_for_testing or datetime.utcnow()):
    save_stats(
        analyze_project_patchset_attempts(
            project_patchset_attempts_for_interval(begin, end)),
        days, begin, end)
    logging.debug('Saved stats from %s to %s.' % (begin, end))
    begin = begin + timedelta(days)
    end = end + timedelta(days)

def next_stats_interval(days): # pragma: no cover
  """Find the next <days> interval that doesn't have CQStats.

  Finds the next interval of CQStats to analyze, if there are no
  CQStats saved yet then start from the earliest Record.
  """
  last_stats = CQStats.query().filter(
      CQStats.interval_days == days).order(-CQStats.end).get()
  if last_stats:
    begin = last_stats.end
  else:
    earliest_record = Record.query().order(Record.timestamp).get()
    stats_start = datetime.utcfromtimestamp(STATS_START_TIMESTAMP)
    begin = stats_start + timedelta(days * math.floor(
      (earliest_record.timestamp - stats_start).total_seconds() //
      timedelta(days).total_seconds()))
  end = begin + timedelta(days)
  return begin, end

def project_patchset_attempts_for_interval(begin, end): # pragma: no cover
  """Structures Records in the interval by project, patchset and CQ attempt.

  Returns per project, per patchset, a list of CQ attempts whose end time
  lies within the specified interval. CQ attempts start with <start_tag>
  and end with <end_tag> and contain all the records relating to that attempt
  between these two markers (inclusive).
  Output format:
  {
    project_name: {
      (issue, patchset): [[Record]]
    },
  }
  """
  finished_in_interval = Record.query().filter(
      Record.tags == stop_tag,
      Record.timestamp >= begin,
      Record.timestamp < end)
  finish_timestamps = {}
  for record in finished_in_interval:
    if all(i in record.fields for i in ('project', 'issue', 'patchset')):
      key = (
        record.fields['project'],
        record.fields['issue'],
        record.fields['patchset'],
      )
      finish_timestamps.setdefault(key, []).append(record.timestamp)
  project_patchset_attempts = {}
  for key in finish_timestamps:
    last_finish_timestamp = max(finish_timestamps[key])
    project, issue, patchset = key
    earliest_start_record = Record.query().order(Record.timestamp).filter(
      Record.tags == project_tag % project,
      Record.tags == issue_tag % issue,
      Record.tags == patchset_tag % patchset).get()
    if not earliest_start_record:
      logging.warning(
          'No start message found for project %s, '
          'issue %s, patchset %s.' % (project, issue, patchset))
      continue
    patchset_attempts = project_patchset_attempts.setdefault(project, {})
    attempts = patchset_attempts.setdefault((issue, patchset), [])
    interval_query = Record.query().order(Record.timestamp).filter(
        Record.timestamp >= earliest_start_record.timestamp,
        Record.timestamp <= last_finish_timestamp,
        Record.tags == project_tag % project,
        Record.tags == issue_tag % issue,
        Record.tags == patchset_tag % patchset)
    attempt = None
    for record in interval_query:
      if attempt == None and start_tag in record.tags:
        attempt = []
      if attempt != None:
        attempt.append(record)
        if stop_tag in record.tags:
          attempts.append(attempt)
          attempt = None
  return project_patchset_attempts

def analyze_project_patchset_attempts(
    project_patchset_attempts): # pragma: no cover
  project_patchsets_stats = {}
  for project, patchset_attempts in project_patchset_attempts.iteritems():
    project_patchsets_stats[project] = []
    for analyzers in analyzer_lists:
      project_patchsets_stats[project].extend(
          analyzer(patchset_attempts) for analyzer in analyzers)
  return project_patchsets_stats

def save_stats(project_patchsets_stats, days, begin, end): # pragma: no cover
  for project, stats_list in project_patchsets_stats.iteritems():
    CQStats(
      interval_days=days,
      begin=begin,
      end=end,
      project=project,
      count_stats=filter(lambda stats: type(stats) == CountStats, stats_list),
      list_stats=filter(lambda stats: type(stats) == ListStats, stats_list),
    ).put()
