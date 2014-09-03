# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import numpy

from google.appengine.ext import ndb

from shared.utils import to_unix_timestamp

class CountStats(ndb.Model): # pragma: no cover
  name = ndb.StringProperty(required=True)
  description = ndb.StringProperty(required=True)
  count = ndb.IntegerProperty(required=True)

  def to_dict(self):
    return {
      'type': 'count',
      'name': self.name,
      'description': self.description,
      'count': self.count,
    }

class ListStats(ndb.Model): # pragma: no cover
  name = ndb.StringProperty(required=True)
  description = ndb.StringProperty(required=True)
  unit = ndb.StringProperty(required=True)
  sample_size = ndb.FloatProperty(default=0)
  min = ndb.FloatProperty(default=0)
  max = ndb.FloatProperty(default=0)
  mean = ndb.FloatProperty(default=0)
  percentile_10 = ndb.FloatProperty(default=0)
  percentile_25 = ndb.FloatProperty(default=0)
  percentile_50 = ndb.FloatProperty(default=0)
  percentile_75 = ndb.FloatProperty(default=0)
  percentile_90 = ndb.FloatProperty(default=0)
  percentile_95 = ndb.FloatProperty(default=0)
  percentile_99 = ndb.FloatProperty(default=0)
  best_10 = ndb.JsonProperty(default=[])
  worst_10 = ndb.JsonProperty(default=[])

  def set_from_points(self, points, lower_is_better=True):
    self.sample_size = len(points)
    sorted_points = sorted(points)
    if points:
      sorted_values = [value for value, _ in sorted_points]
      if lower_is_better:
        self.best_10 = sorted_points[:10]
        self.worst_10 = sorted_points[-10:][::-1]
      else:
        self.best_10 = sorted_points[-10:][::-1]
        self.worst_10 = sorted_points[:10]
    else:
      # Use 0 as a default value for the numeric stats.
      sorted_values = [0]
      self.best_10 = []
      self.worst_10 = []
    self.min = sorted_values[0]
    self.max = sorted_values[-1]
    self.mean = numpy.mean(sorted_values)
    self.percentile_10 = numpy.percentile(sorted_values, 10)
    self.percentile_25 = numpy.percentile(sorted_values, 25)
    self.percentile_50 = numpy.percentile(sorted_values, 50)
    self.percentile_75 = numpy.percentile(sorted_values, 75)
    self.percentile_90 = numpy.percentile(sorted_values, 90)
    self.percentile_95 = numpy.percentile(sorted_values, 95)
    self.percentile_99 = numpy.percentile(sorted_values, 99)

  def to_dict(self):
    return {
      'type': 'list',
      'name': self.name,
      'description': self.description,
      'unit': self.unit,
      'sample_size': self.sample_size,
      'min': self.min,
      'max': self.max,
      'mean': self.mean,
      'percentile_10': self.percentile_10,
      'percentile_25': self.percentile_25,
      'percentile_50': self.percentile_50,
      'percentile_75': self.percentile_75,
      'percentile_90': self.percentile_90,
      'percentile_95': self.percentile_95,
      'percentile_99': self.percentile_99,
      'best_10': self.best_10,
      'worst_10': self.worst_10,
    }

class CQStats(ndb.Model): # pragma: no cover
  project = ndb.StringProperty(required=True)
  interval_days = ndb.IntegerProperty(required=True)
  begin = ndb.DateTimeProperty(required=True)
  end = ndb.DateTimeProperty(required=True)
  count_stats = ndb.StructuredProperty(CountStats, repeated=True)
  list_stats = ndb.StructuredProperty(ListStats, repeated=True)

  def to_dict(self, name_filter=None):
    """Returns a JSON friendly dict

    If the name filter is falsey it is ignored.
    """
    def combined_stats():
      for stats in self.count_stats + self.list_stats:
        if not name_filter or stats.name in name_filter:
          yield stats.to_dict()
    return {
      'interval_days': self.interval_days,
      'begin': to_unix_timestamp(self.begin),
      'end': to_unix_timestamp(self.end),
      'project': self.project,
      'stats': list(combined_stats()),
    }

  def has_any_names(self, names):
    for stats in self.count_stats + self.list_stats:
      if stats.name in names:
        return True
    return False
