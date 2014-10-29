# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
from datetime import datetime, timedelta
import logging
import math

from google.appengine.ext import ndb

from model.cq_stats import (
  CountStats,
  CQStats,
  ListStats,
)
from model.record import Record
from shared.config import (
  STATS_START_TIMESTAMP,
  TAG_START,
  TAG_STOP,
  TAG_PROJECT,
  TAG_ISSUE,
  TAG_PATCHSET,
)
from stats.analyzer import AnalyzerGroup

PatchsetReference = namedtuple('PatchsetReference', 'issue patchset')
stats_start = datetime.utcfromtimestamp(STATS_START_TIMESTAMP)

def intervals_in_range(minutes, begin, end): # pragma: no cover
  """Return all analysis intervals of length <minutes> that lie inside
  <begin> and <end> inclusive."""
  interval_begin = stats_start + timedelta(minutes=minutes * math.ceil(
      (begin - stats_start).total_seconds() / (minutes * 60.0)))
  intervals = []
  while True:
    interval_end = interval_begin + timedelta(minutes=minutes)
    if interval_end > end:
      return intervals
    intervals.append((interval_begin, interval_end))
    interval_begin = interval_end

def update_interval(minutes, begin, end, analyzer_classes): # pragma: no cover
  """Analyze stats over the given interval for all projects and update CQStats.
  """
  logging.debug('Updating stats from %s to %s using analyzers: %s.' % (
      begin, end, analyzer_classes))
  stats = analyze_attempts(attempts_for_interval(begin, end), analyzer_classes)
  logging.debug('Analyzed stats.')
  update_cq_stats(stats, minutes, begin, end)
  logging.debug('Saved stats.')
  begin = begin + timedelta(minutes=minutes)
  end = end + timedelta(minutes=minutes)

def attempts_for_interval(begin, end): # pragma: no cover
  finished_in_interval = Record.query().filter(
      Record.tags == TAG_STOP,
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
    earliest_record = Record.query().order(Record.timestamp).filter(
      Record.tags == TAG_PROJECT % project,
      Record.tags == TAG_ISSUE % issue,
      Record.tags == TAG_PATCHSET % patchset).get()
    if not earliest_record:
      logging.warning(
          'No start message found for project %s, '
          'issue %s, patchset %s.' % (project, issue, patchset))
      continue
    interval_query = Record.query().order(Record.timestamp).filter(
        Record.timestamp >= earliest_record.timestamp,
        Record.timestamp <= last_finish_timestamp,
        Record.tags == TAG_PROJECT % project,
        Record.tags == TAG_ISSUE % issue,
        Record.tags == TAG_PATCHSET % patchset)
    all_attempts = []
    interval_attempts = []
    attempt = None
    for record in interval_query:
      if TAG_START in record.tags:
        attempt = []
      if attempt != None:
        attempt.append(record)
        if TAG_STOP in record.tags:
          if record.timestamp >= begin:
            interval_attempts.append(attempt)
          all_attempts.append(attempt)
          attempt = None
    if len(all_attempts) == 0:
      logging.warning('No attempts found for %s issue %s patchset %s at %s' %
          (project, issue, patchset, begin))
      continue
    yield project, issue, patchset, all_attempts, interval_attempts

def analyze_attempts(attempts_iterator, analyzer_classes): # pragma: no cover
  """Split attempts by project and feed to project specific analyzer instances.
  """
  project_analyzers = {}
  for project, issue, patchset, all_attempts, interval_attempts in attempts_iterator: # pylint: disable=C0301
    if project not in project_analyzers:
      project_analyzers[project] = AnalyzerGroup(*analyzer_classes)
    project_analyzers[project].new_attempts(project,
        PatchsetReference(issue, patchset), all_attempts, interval_attempts)
  project_stats = {}
  for project, analyzer in project_analyzers.iteritems():
    project_stats[project] = analyzer.build_stats()
  return project_stats

def update_cq_stats(project_stats, minutes, begin, end): # pragma: no cover
  """Ensure CQStats are updated or created as necessary with new stats data."""
  assert (end - begin).total_seconds() == 60 * minutes
  assert (begin - stats_start).total_seconds() % (60 * minutes) == 0, (
      'Interval must be aligned with %s.' % stats_start)
  for project, stats_list in project_stats.iteritems():
    count_stats_dict = {}
    list_stats_dict = {}
    for stats in stats_list:
      if type(stats) == CountStats:
        count_stats_dict[stats.name] = stats
      else:
        assert type(stats) == ListStats
        list_stats_dict[stats.name] = stats

    cq_stats = CQStats.query().filter(
        CQStats.project == project,
        CQStats.interval_minutes == minutes,
        CQStats.begin == begin).get()
    if cq_stats:
      update_stats_list(cq_stats.count_stats, count_stats_dict)
      update_stats_list(cq_stats.list_stats, list_stats_dict)
      cq_stats.put()
    else:
      CQStats(
        project=project,
        interval_minutes=minutes,
        begin=begin,
        end=end,
        count_stats=count_stats_dict.values(),
        list_stats=list_stats_dict.values(),
      ).put()

def update_stats_list(existing_stats_list, new_stats_dict): # pragma: no cover
  for i, stats in enumerate(existing_stats_list):
    name = stats.name
    if name in new_stats_dict:
      existing_stats_list[i] = new_stats_dict[name]
      del new_stats_dict[name]
  existing_stats_list.extend(new_stats_dict.values())
