# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta
import logging
import math

from google.appengine.ext import ndb

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

def analyze_interval(minutes): # pragma: no cover
  """Build and save CQStats for every <minutes> interval in Records.

  Walks forwards through the Records history <minutes> at a time,
  analyzing and saving CQStats for each interval.
  """
  if Record.query().count(1) == 0:
    return
  logging.debug('Analyzing records %s minutes at a time' % minutes)
  begin, end = next_stats_interval(minutes)
  while end <= (utcnow_for_testing or datetime.utcnow()):
    logging.debug('Updating stats from %s to %s.' % (begin, end))
    save_stats(analyze_attempts(attempts_for_interval(begin, end)),
        minutes, begin, end)
    logging.debug('Saved stats.')
    begin = begin + timedelta(minutes=minutes)
    end = end + timedelta(minutes=minutes)

def next_stats_interval(minutes): # pragma: no cover
  """Find the next <minutes> interval that doesn't have CQStats.

  Finds the next interval of CQStats to analyze, if there are no
  CQStats saved yet then start from the earliest Record.
  """
  last_stats = CQStats.query().filter(
      CQStats.interval_minutes == minutes).order(-CQStats.end).get()
  if last_stats:
    begin = last_stats.end
  else:
    earliest_record = Record.query().order(Record.timestamp).get()
    stats_start = datetime.utcfromtimestamp(STATS_START_TIMESTAMP)
    begin = stats_start + timedelta(minutes=minutes * math.floor(
      (earliest_record.timestamp - stats_start).total_seconds() //
      timedelta(minutes=minutes).total_seconds()))
    if begin < stats_start:
      begin = stats_start
  end = begin + timedelta(minutes=minutes)
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
    # NDB seems to cache records beyond the soft memory limit.
    # Force a cache clear between each patchset analysis run to avoid getting
    # terminated by Appengine.
    ndb.get_context().clear_cache()

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

def save_stats(project_stats, minutes, begin, end): # pragma: no cover
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
      interval_minutes=minutes,
      begin=begin,
      end=end,
      count_stats=count_stats,
      list_stats=list_stats,
    ).put()
