# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import numpy

from google.appengine.ext import ndb

class NumberListStats(ndb.Model):
  length = ndb.FloatProperty(default=0)
  min = ndb.FloatProperty(default=0)
  max = ndb.FloatProperty(default=0)
  mean = ndb.FloatProperty(default=0)
  p10 = ndb.FloatProperty(default=0)
  p25 = ndb.FloatProperty(default=0)
  p50 = ndb.FloatProperty(default=0)
  p75 = ndb.FloatProperty(default=0)
  p90 = ndb.FloatProperty(default=0)
  p95 = ndb.FloatProperty(default=0)
  p99 = ndb.FloatProperty(default=0)

  @classmethod
  def from_list(cls, number_list): # pragma: no cover
    stats = NumberListStats()
    if not number_list:
      return stats
    sorted_list = sorted(number_list)
    stats.length = len(sorted_list)
    stats.min = sorted_list[0]
    stats.max = sorted_list[-1]
    stats.mean = numpy.mean(sorted_list)
    stats.p10 = numpy.percentile(sorted_list, 10)
    stats.p25 = numpy.percentile(sorted_list, 25)
    stats.p50 = numpy.percentile(sorted_list, 50)
    stats.p75 = numpy.percentile(sorted_list, 75)
    stats.p90 = numpy.percentile(sorted_list, 90)
    stats.p95 = numpy.percentile(sorted_list, 95)
    stats.p99 = numpy.percentile(sorted_list, 99)
    return stats

class CQStats(ndb.Model):
  interval_days = ndb.IntegerProperty(required=True)
  begin = ndb.DateTimeProperty(required=True)
  end = ndb.DateTimeProperty(required=True)
  project = ndb.StringProperty(required=True)
  patchset_count = ndb.IntegerProperty(required=True)
  patchset_success_count = ndb.IntegerProperty(required=True)
  patchset_run_counts = \
      ndb.StructuredProperty(NumberListStats, required=True)
  patchset_false_rejections = \
      ndb.StructuredProperty(NumberListStats, required=True)
  run_count = ndb.IntegerProperty(required=True)
  run_success_count = ndb.IntegerProperty(required=True)
  run_seconds = ndb.StructuredProperty(NumberListStats, required=True)

class CQStatsGroup(ndb.Model):
  pass
