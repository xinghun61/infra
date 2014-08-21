# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
from datetime import datetime, timedelta
import logging
import math

from google.appengine.ext import ndb

from model.cq_stats import ( # pylint: disable-msg=E0611
  CQStats,
  CQStatsGroup,
  NumberListStats,
)
from model.record import Record # pylint: disable-msg=E0611
from shared.config import STATS_START_TIMESTAMP

issue_tag = 'issue=%s'
patchset_tag = 'patchset=%s'
start_tag = 'verification=initial'
success_tag = 'verification=commit'
failure_tag = 'verification=abort'
start_event, success_event, failure_event = range(3)

utcnow_for_testing = None

def analyze_interval(days): # pragma: no cover
  """
  Walks forwards through the Records history <days> at a time
  analyzing and saving CQStats for each interval.
  """
  if Record.query().count(1) == 0:
    return
  begin, end = next_stats_interval(days)
  while end < (utcnow_for_testing or datetime.utcnow()):
    project_events = project_events_for_interval(begin, end)
    analyze_and_save_stats(project_events, days, begin, end,
        CQStatsGroup().put())
    begin = begin + timedelta(days)
    end = end + timedelta(days)

def next_stats_interval(days): # pragma: no cover
  """
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

def project_events_for_interval(begin, end): # pragma: no cover
  """
  Scrapes through Records in the given range and picks out start, success and
  failure events per patchset per project and returns the data in the following
  project_events format:
  {
    project_name: {
      (issue, patchset): [
        (timestamp, event)
      ]
    },
  }
  """
  interval_query = Record.query().filter(
      Record.timestamp >= begin, Record.timestamp < end)
  project_events = defaultdict(lambda: defaultdict(list))
  for record in interval_query.filter(Record.tags == success_tag):
    add_event(project_events, record, success_event)
  for record in interval_query.filter(Record.tags == failure_tag):
    add_event(project_events, record, failure_event)
  before_end_query = Record.query().filter(Record.timestamp < end)
  for project in project_events:
    for issue, patchset in project_events[project]:
      for record in before_end_query.filter(
          Record.tags == start_tag,
          Record.tags == (issue_tag % issue),
          Record.tags == (patchset_tag % patchset)):
        add_event(project_events, record, start_event)
  for project in project_events:
    for key in project_events[project]:
      project_events[project][key].sort()
  return project_events

def add_event(project_events, record, event): # pragma: no cover
  for field in ('project', 'issue', 'patchset'):
    if field not in record.fields:
      logging.warning('Record %s at %s missing field %s' %
          (record.key.id(), record.timestamp, field))
      return
  project = record.fields['project']
  issue = record.fields['issue']
  patchset = record.fields['patchset']
  project_events[project][(issue, patchset)].append((record.timestamp, event))

@ndb.transactional
def analyze_and_save_stats(project_events, days, begin, end,
    transaction_group): # pragma: no cover
  """
  Scans through per patchset events to build statistics and saves them to the
  database.
  """
  for project, patchset_events in project_events.items():
    patchset_count = 0
    patchset_success_count = 0
    patchset_run_counts = []
    patchset_false_rejections = []
    run_count = 0
    run_success_count = 0
    run_seconds = []
    for (issue, patchset), timestamped_events in patchset_events.items():
      patchset_count += 1
      patchset_run_count = 0
      patchset_successful = False
      patchset_run_failure_streak = 0
      patchset_false_rejection_count = 0
      last_timestamp = None
      last_event = None
      for timestamp, event in timestamped_events:
        if last_event == start_event:
          if event in (success_event, failure_event):
            if event == success_event:
              patchset_successful = True
              run_success_count += 1
              patchset_false_rejection_count += patchset_run_failure_streak
              patchset_run_failure_streak = 0
            else:
              patchset_run_failure_streak += 1
            patchset_run_count += 1
            run_seconds.append((timestamp - last_timestamp).total_seconds())
          elif last_timestamp >= begin:
            logging.warning(
                ('Unexpected event sequence for '
                 'issue %s, patchset %s, project %s: %s') %
                (issue, patchset, project, timestamped_events))
        last_timestamp = timestamp
        last_event = event
      patchset_run_counts.append(patchset_run_count)
      patchset_success_count += int(patchset_successful)
      patchset_false_rejections.append(patchset_false_rejection_count)
      run_count += patchset_run_count
    CQStats(
      parent=transaction_group,
      interval_days=days,
      begin=begin,
      end=end,
      project=project,
      patchset_count=patchset_count,
      patchset_success_count=patchset_success_count,
      patchset_run_counts=NumberListStats.from_list(patchset_run_counts),
      patchset_false_rejections=
          NumberListStats.from_list(patchset_false_rejections),
      run_count=run_count,
      run_success_count=run_success_count,
      run_seconds=NumberListStats.from_list(run_seconds),
    ).put()
