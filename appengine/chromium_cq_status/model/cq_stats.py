# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import numpy

from google.appengine.ext import ndb

class CountStats(ndb.Model): # pragma: no cover
  name = ndb.StringProperty(required=True)
  description = ndb.StringProperty()
  count = ndb.IntegerProperty(required=True)

  @staticmethod
  def constructor(description):
    def decorator(count_function):
      def create_count_stats(patchset_attempts):
        return CountStats(
          name=count_function.func_name,
          description=description,
          count=count_function(patchset_attempts),
        )
      return create_count_stats
    return decorator

  def to_dict(self):
    return {
      'type': 'count',
      'name': self.name,
      'description': self.description,
      'count': self.count,
    }

class ListStats(ndb.Model): # pragma: no cover
  name = ndb.StringProperty(required=True)
  description = ndb.StringProperty()
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

  @staticmethod
  def constructor(description, unit, lower_is_better=True):
    def decorator(points_function):
      """points_function must return a [(value, metadata)]"""
      def create_list_stats(patchset_attempts):
        points = points_function(patchset_attempts)
        sorted_points = sorted(points)
        if sorted_points:
          sorted_values = [value for value, _ in sorted_points]
        else:
          # Use 0 as a default value for the numeric stats.
          sorted_values = [0]
        if lower_is_better:
          best_10 = sorted_points[:10]
          worst_10 = sorted_points[-10:][::-1]
        else:
          best_10 = sorted_points[-10:][::-1]
          worst_10 = sorted_points[:10]
        return ListStats(
          name=points_function.func_name,
          description=description,
          unit=unit,
          sample_size=len(points),
          min=sorted_values[0],
          max=sorted_values[-1],
          mean=numpy.mean(sorted_values),
          percentile_10=numpy.percentile(sorted_values, 10),
          percentile_25=numpy.percentile(sorted_values, 25),
          percentile_50=numpy.percentile(sorted_values, 50),
          percentile_75=numpy.percentile(sorted_values, 75),
          percentile_90=numpy.percentile(sorted_values, 90),
          percentile_95=numpy.percentile(sorted_values, 95),
          percentile_99=numpy.percentile(sorted_values, 99),
          best_10=best_10,
          worst_10=worst_10,
        )
      return create_list_stats
    return decorator

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
  interval_days = ndb.IntegerProperty(required=True)
  begin = ndb.DateTimeProperty(required=True)
  end = ndb.DateTimeProperty(required=True)
  project = ndb.StringProperty(required=True)
  stats_names = ndb.StringProperty(repeated=True)
  count_stats = ndb.StructuredProperty(CountStats, repeated=True)
  list_stats = ndb.StructuredProperty(ListStats, repeated=True)

  def to_dict(self):
    stats = [stats.to_dict() for stats in self.count_stats + self.list_stats]
    return {
      'interval_days': self.interval_days,
      'begin': calendar.timegm(self.begin.timetuple()),
      'end': calendar.timegm(self.end.timetuple()),
      'project': self.project,
      'stats': stats,
    }
