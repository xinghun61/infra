# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta
import webapp2

from model.cq_stats import CQStats
from model.record import Record
from shared.utils import cronjob
from stats.analysis import (
  intervals_in_range,
  update_interval,
)
from stats.patchset_stats import PatchsetAnalyzer
from stats.trybot_stats import TrybotAnalyzer
from stats.tryjobverifier_stats import TryjobverifierAnalyzer

analyzer_classes = (
  PatchsetAnalyzer,
  TrybotAnalyzer,
  TryjobverifierAnalyzer,
)

def update_missing_cq_stats(minutes, end): # pragma: no cover
  for begin, end in missing_intervals(minutes, end):
    update_interval(minutes, begin, end, analyzer_classes)

def missing_intervals(minutes, end): # pragma: no cover
  last_cq_stats = CQStats.query().filter(
      CQStats.interval_minutes == minutes).order(-CQStats.end).get()
  if last_cq_stats:
    return intervals_in_range(minutes, last_cq_stats.end, end)
  earliest_record = Record.query().order(Record.timestamp).get()
  if earliest_record:
    begin = earliest_record.timestamp - timedelta(minutes=minutes)
    return intervals_in_range(minutes, begin, end)
  return []

class UpdateStats(webapp2.RequestHandler): # pragma: no cover
  @cronjob
  def get(self):
    update_missing_cq_stats(
        int(self.request.get('interval_minutes')), datetime.utcnow())
