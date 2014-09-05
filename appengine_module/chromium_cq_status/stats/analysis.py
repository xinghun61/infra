# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta
import logging
import math

from appengine_module.chromium_cq_status.model.cq_stats import (
  CountStats,
  CQStats,
  ListStats,
)
from appengine_module.chromium_cq_status.model.record import Record
from appengine_module.chromium_cq_status.shared.config import STATS_START_TIMESTAMP  # pylint: disable=C0301
from appengine_module.chromium_cq_status.stats.analyzer import AnalyzerGroup
from appengine_module.chromium_cq_status.stats.patchset_stats import PatchsetAnalyzer  # pylint: disable=C0301
from appengine_module.chromium_cq_status.stats.tryjobverifier_stats import TryjobverifierAnalyzer  # pylint: disable=C0301

start_tag = 'action=patch_start'
stop_tag = 'action=patch_stop'
project_tag = 'project=%s'
issue_tag = 'issue=%s'
patchset_tag = 'patchset=%s'

utcnow_for_testing = None

analyzers = (
  PatchsetAnalyzer,
  TryjobverifierAnalyzer,
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
  while end <= (utcnow_for_testing or datetime.utcnow()):
    logging.debug('Updating stats from %s to %s.' % (begin, end))
    save_stats(analyze_attempts(attempts_for_interval(begin, end)),
        days, begin, end)
    logging.debug('Saved stats.')
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
    if begin < stats_start:
      begin = stats_start
  end = begin + timedelta(days)
  return begin, end

def attempts_for_interval(begin, end): # pragma: no cover
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
    interval_query = Record.query().order(Record.timestamp).filter(
        Record.timestamp >= earliest_start_record.timestamp,
        Record.timestamp <= last_finish_timestamp,
        Record.tags == project_tag % project,
        Record.tags == issue_tag % issue,
        Record.tags == patchset_tag % patchset)
    attempts = []
    attempt = None
    for record in interval_query:
      if start_tag in record.tags:
        attempt = []
      if attempt != None:
        attempt.append(record)
        if stop_tag in record.tags:
          if record.timestamp >= begin:
            attempts.append(attempt)
          attempt = None
    yield project, issue, patchset, attempts

def analyze_attempts(attempts_iterator): # pragma: no cover
  logging.debug('Analyzing CQ attempts.')
  project_analyzers = {}
  for project, issue, patchset, attempts in attempts_iterator:
    if project not in project_analyzers:
      project_analyzers[project] = AnalyzerGroup(*analyzers)
    project_analyzers[project].new_patchset_attempts(issue, patchset, attempts)
  project_stats = {}
  for project, analyzer in project_analyzers.iteritems():
    project_stats[project] = analyzer.build_stats()
  return project_stats

def save_stats(project_stats, days, begin, end): # pragma: no cover
  logging.debug('Saving stats.')
  for project, stats_list in project_stats.iteritems():
    count_stats = []
    list_stats = []
    for stats in stats_list:
      if type(stats) == CountStats:
        count_stats.append(stats)
      else:
        assert type(stats) == ListStats
        list_stats.append(stats)
    CQStats(
      project=project,
      interval_days=days,
      begin=begin,
      end=end,
      count_stats=count_stats,
      list_stats=list_stats,
    ).put()
